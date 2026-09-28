import os
import sys
# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, send_from_directory
from flask_cors import CORS
from sqlalchemy import inspect, text
from src.models.user import db
from src.routes.user import user_bp
from src.routes.note import note_bp
from src.models.note import Note

ROOT_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

# Static frontend lives in the top-level public/ dir (Vercel serves this
# directory from its CDN directly; Flask also serves it for local dev via
# the catch-all route below).
app = Flask(__name__, static_folder=os.path.join(ROOT_DIR, 'public'))
app.config['SECRET_KEY'] = 'asdf#FGSgvasgf$5$WGT'

# Enable CORS for all routes
CORS(app)

# register blueprints
app.register_blueprint(user_bp, url_prefix='/api')
app.register_blueprint(note_bp, url_prefix='/api')

# Database: use an external Postgres database (e.g. Neon) when DATABASE_URL
# is set - required on Vercel, whose serverless functions have an ephemeral
# filesystem and can't rely on a local SQLite file. Falls back to a local
# SQLite file for convenience when no DATABASE_URL is configured.
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    # SQLAlchemy/psycopg2 expect the "postgresql://" scheme; some providers
    # (and Heroku-style env vars) still hand out the older "postgres://" one.
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
else:
    DB_PATH = os.path.join(ROOT_DIR, 'database', 'app.db')
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{DB_PATH}"

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)


def _ensure_schema():
    """db.create_all() only creates tables that don't exist yet - it never
    alters an existing table, so adding a new model column (e.g. Note.tags)
    does nothing for a database that already has a `note` table. There's no
    migration framework in this small app, so patch that gap here: add any
    columns the model declares but the table is still missing, using each
    column's actual SQLAlchemy type so this keeps working for whatever gets
    added next, not just today's `tags` column.
    """
    inspector = inspect(db.engine)
    if 'note' not in inspector.get_table_names():
        return  # create_all() will make the whole table, columns included

    existing_columns = {col['name'] for col in inspector.get_columns('note')}
    with db.engine.begin() as conn:
        for column in Note.__table__.columns:
            if column.name in existing_columns:
                continue
            column_type = column.type.compile(dialect=db.engine.dialect)
            conn.execute(text(f'ALTER TABLE note ADD COLUMN "{column.name}" {column_type}'))


with app.app_context():
    db.create_all()
    _ensure_schema()

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    static_folder_path = app.static_folder
    if static_folder_path is None:
            return "Static folder not configured", 404

    if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)
    else:
        index_path = os.path.join(static_folder_path, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, 'index.html')
        else:
            return "index.html not found", 404


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
