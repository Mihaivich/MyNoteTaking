"""Upload/delete note attachments (images, documents) using Supabase
Storage's REST API.

(We originally targeted Neon Object Storage, which is S3-compatible - but
its S3 gateway returned a bare 403 on every write during testing, even for
a presigned URL generated and signed by Neon's own backend and hit directly
server-to-server (no CORS involved). Since even Neon's own Console UI
couldn't complete an upload either, that pointed to a platform-side issue
rather than anything in this app, so we switched providers.)
"""

import os
import uuid

import requests

BUCKET = os.environ.get('ATTACHMENTS_BUCKET', 'notetaker-attachments')


class StorageError(Exception):
    """Raised when an attachment could not be stored or removed."""


def is_configured() -> bool:
    return bool(os.environ.get('SUPABASE_URL') and os.environ.get('SUPABASE_SERVICE_KEY'))


def _require_config():
    url = os.environ.get('SUPABASE_URL')
    key = os.environ.get('SUPABASE_SERVICE_KEY')
    if not url or not key:
        raise StorageError(
            "Object storage is not configured. Set SUPABASE_URL and "
            "SUPABASE_SERVICE_KEY (from a Supabase project's API settings)."
        )
    return url.rstrip('/'), key


def upload_attachment(note_id: int, file_storage) -> dict:
    """Upload a Werkzeug FileStorage object for `note_id`.

    Returns {storage_key, url, filename, content_type, size}.
    """
    base_url, service_key = _require_config()

    original_name = file_storage.filename or 'file'
    ext = os.path.splitext(original_name)[1]
    storage_key = f"notes/{note_id}/{uuid.uuid4().hex}{ext}"

    content_type = file_storage.content_type or 'application/octet-stream'
    body = file_storage.read()

    upload_url = f"{base_url}/storage/v1/object/{BUCKET}/{storage_key}"
    try:
        response = requests.post(
            upload_url,
            headers={
                'Authorization': f'Bearer {service_key}',
                'apikey': service_key,
                'Content-Type': content_type,
            },
            data=body,
            timeout=30,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        detail = getattr(exc, 'response', None)
        detail_text = detail.text if detail is not None else str(exc)
        raise StorageError(f"Failed to upload attachment: {detail_text}") from exc

    url = f"{base_url}/storage/v1/object/public/{BUCKET}/{storage_key}"

    return {
        'storage_key': storage_key,
        'url': url,
        'filename': original_name,
        'content_type': content_type,
        'size': len(body),
    }


def delete_attachment(storage_key: str) -> None:
    base_url, service_key = _require_config()
    delete_url = f"{base_url}/storage/v1/object/{BUCKET}/{storage_key}"
    try:
        response = requests.delete(
            delete_url,
            headers={
                'Authorization': f'Bearer {service_key}',
                'apikey': service_key,
            },
            timeout=30,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        detail = getattr(exc, 'response', None)
        detail_text = detail.text if detail is not None else str(exc)
        raise StorageError(f"Failed to delete attachment: {detail_text}") from exc
