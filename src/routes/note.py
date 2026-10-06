from flask import Blueprint, jsonify, request
from src.models.note import Note, Attachment, db
from src.services.translation_service import TranslationError, translate_note
from src.services.note_ai_service import NoteAIError, generate_title_and_tags
from src.services import storage_service
from src.services.storage_service import StorageError

note_bp = Blueprint('note', __name__)

MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_CONTENT_TYPES = {
    'image/png', 'image/jpeg', 'image/gif', 'image/webp', 'image/svg+xml',
    'application/pdf', 'text/plain',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
}

@note_bp.route('/notes', methods=['GET'])
def get_notes():
    """Get all notes, ordered by most recently updated"""
    notes = Note.query.order_by(Note.updated_at.desc()).all()
    return jsonify([note.to_dict() for note in notes])

@note_bp.route('/notes', methods=['POST'])
def create_note():
    """Create a new note.

    If title is blank but there's content to work with, ask an LLM to
    suggest a title and a few tags rather than leaving it "Untitled" - see
    src/services/note_ai_service.py. Best-effort: falls back to "Untitled"
    with no tags if that fails (missing key, model error, etc).
    """
    try:
        data = request.json
        if not data or 'title' not in data or 'content' not in data:
            return jsonify({'error': 'Title and content are required'}), 400

        title = (data['title'] or '').strip()
        content = data['content']
        tags = data.get('tags') or []
        ai_generated_title = False

        if not title and content.strip():
            try:
                suggestion = generate_title_and_tags(content)
                title = suggestion['title']
                if not tags:
                    tags = suggestion['tags']
                ai_generated_title = True
            except NoteAIError:
                pass  # fall through to the plain "Untitled" default below

        note = Note(title=title or 'Untitled', content=content, tags=tags)
        db.session.add(note)
        db.session.commit()

        result = note.to_dict()
        result['ai_generated_title'] = ai_generated_title
        return jsonify(result), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@note_bp.route('/notes/<int:note_id>', methods=['GET'])
def get_note(note_id):
    """Get a specific note by ID"""
    note = Note.query.get_or_404(note_id)
    return jsonify(note.to_dict())

@note_bp.route('/notes/<int:note_id>', methods=['PUT'])
def update_note(note_id):
    """Update a specific note"""
    try:
        note = Note.query.get_or_404(note_id)
        data = request.json
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Fall back to the existing title if an empty one is sent (e.g. the
        # frontend now sends the raw, possibly-blank title so a *new* note
        # can trigger AI auto-titling - an update shouldn't blank out an
        # already-saved note's title the same way).
        note.title = data.get('title') or note.title
        note.content = data.get('content', note.content)
        if 'tags' in data:
            note.tags = data.get('tags') or []
        db.session.commit()
        return jsonify(note.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@note_bp.route('/notes/<int:note_id>', methods=['DELETE'])
def delete_note(note_id):
    """Delete a specific note (and its attachments, from storage and DB)"""
    try:
        note = Note.query.get_or_404(note_id)
        for attachment in note.attachments:
            try:
                storage_service.delete_attachment(attachment.storage_key)
            except StorageError:
                # Don't block note deletion on a storage hiccup - the DB
                # row (and thus the dangling object's only reference) is
                # removed either way.
                pass
        db.session.delete(note)
        db.session.commit()
        return '', 204
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@note_bp.route('/notes/<int:note_id>/translate', methods=['POST'])
def translate_note_route(note_id):
    """Translate a note's title/content into a target language via an LLM.

    Body (optional): {"target_language": "Chinese (Simplified)"}
    Response (JSON): {translated_title, translated_content, target_language}
    This does not modify the stored note - it's a read-only translation.
    """
    note = Note.query.get_or_404(note_id)
    data = request.json if request.is_json else {}
    target_language = (data or {}).get('target_language')

    try:
        result = translate_note(note.title, note.content, target_language)
        return jsonify(result)
    except TranslationError as e:
        return jsonify({'error': str(e)}), 502

@note_bp.route('/notes/<int:note_id>/attachments', methods=['POST'])
def upload_attachment(note_id):
    """Attach an image/document to a note.

    multipart/form-data with a single "file" field. Stores the file in an
    S3-compatible object store (Neon Object Storage) and records metadata
    in the attachment table.
    """
    note = Note.query.get_or_404(note_id)

    if not storage_service.is_configured():
        return jsonify({'error': 'Object storage is not configured on the server'}), 501

    file_storage = request.files.get('file')
    if not file_storage or not file_storage.filename:
        return jsonify({'error': 'No file provided'}), 400

    content_type = file_storage.content_type or 'application/octet-stream'
    if content_type not in ALLOWED_CONTENT_TYPES:
        return jsonify({'error': f'Unsupported file type: {content_type}'}), 400

    # Peek at size without fully committing to it (content_length is a
    # client-provided hint; storage_service re-measures the real body too).
    file_storage.stream.seek(0, 2)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size > MAX_ATTACHMENT_SIZE:
        return jsonify({'error': f'File too large (max {MAX_ATTACHMENT_SIZE // (1024 * 1024)}MB)'}), 400

    try:
        uploaded = storage_service.upload_attachment(note_id, file_storage)
    except StorageError as e:
        return jsonify({'error': str(e)}), 502

    try:
        attachment = Attachment(
            note_id=note.id,
            filename=uploaded['filename'],
            content_type=uploaded['content_type'],
            size=uploaded['size'],
            storage_key=uploaded['storage_key'],
            url=uploaded['url'],
        )
        db.session.add(attachment)
        db.session.commit()
        return jsonify(attachment.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        # Best-effort cleanup of the now-orphaned object in storage.
        try:
            storage_service.delete_attachment(uploaded['storage_key'])
        except StorageError:
            pass
        return jsonify({'error': str(e)}), 500

@note_bp.route('/attachments/<int:attachment_id>', methods=['DELETE'])
def delete_attachment(attachment_id):
    """Delete a single attachment from storage and the database"""
    attachment = Attachment.query.get_or_404(attachment_id)
    try:
        storage_service.delete_attachment(attachment.storage_key)
    except StorageError as e:
        return jsonify({'error': str(e)}), 502

    try:
        db.session.delete(attachment)
        db.session.commit()
        return '', 204
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@note_bp.route('/notes/search', methods=['GET'])
def search_notes():
    """Search notes by title or content"""
    query = request.args.get('q', '')
    if not query:
        return jsonify([])
    
    notes = Note.query.filter(
        (Note.title.contains(query)) | (Note.content.contains(query))
    ).order_by(Note.updated_at.desc()).all()

    return jsonify([note.to_dict() for note in notes])

@note_bp.route('/keepalive', methods=['GET'])
def keepalive():
    """Hit by a Vercel Cron Job (see vercel.json) so Supabase doesn't
    auto-pause this project for inactivity."""
    try:
        storage_service.ping()
        return jsonify({'status': 'ok'})
    except StorageError as e:
        return jsonify({'status': 'error', 'error': str(e)}), 502

