from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from src.models.user import db

class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    # Nullable so this new column doesn't break rows that existed in the
    # database before it was added (see _ensure_schema in src/main.py).
    tags = db.Column(db.JSON, nullable=True, default=list)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    attachments = db.relationship(
        'Attachment', backref='note', cascade='all, delete-orphan',
        order_by='Attachment.created_at'
    )

    def __repr__(self):
        return f'<Note {self.title}>'

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'tags': self.tags or [],
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'attachments': [a.to_dict() for a in self.attachments]
        }


class Attachment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    note_id = db.Column(db.Integer, db.ForeignKey('note.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    content_type = db.Column(db.String(100), nullable=False)
    size = db.Column(db.Integer, nullable=False)
    storage_key = db.Column(db.String(500), nullable=False)
    url = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Attachment {self.filename}>'

    def to_dict(self):
        return {
            'id': self.id,
            'note_id': self.note_id,
            'filename': self.filename,
            'content_type': self.content_type,
            'size': self.size,
            'url': self.url,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

