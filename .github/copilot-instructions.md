# Copilot / AI coding agent instructions for NoteTaker

## Project overview
Flask + vanilla JS note-taking app.
- Backend: `src/main.py` (app entry), `src/routes/*.py` (Blueprints), `src/models/*.py`
  (SQLAlchemy models), `src/services/*.py` (business logic, e.g. LLM calls).
- Frontend: a single file, `src/static/index.html` (HTML + CSS + vanilla JS, no
  build step, no framework). Keep it that way unless explicitly asked to
  introduce a frontend framework/bundler.
- Database: SQLite at `database/app.db`, created automatically on startup.
  Never commit `*.db` files.

## Coding conventions
- Backend: standard Flask blueprint style already used in `src/routes/note.py`
  — one function per route, `try/except` around DB writes with
  `db.session.rollback()` on failure, JSON error responses shaped like
  `{"error": "..."}`.
- Frontend: the app is one JS class (`NoteTaker`) in `index.html` that owns
  all state (`this.notes`, `this.currentNote`) and DOM wiring in
  `bindEvents()`. Add new UI behavior as methods on this class rather than
  ad-hoc global functions.
- Don't remove the `# DON'T CHANGE THIS !!!` `sys.path.insert(...)` line at
  the top of `src/main.py` — it makes the `src.*` imports work when running
  `python src/main.py` directly.

## Secrets and configuration
- Any API key or secret goes in `.env` (already gitignored) and is read via
  `os.getenv(...)`. Never hard-code keys in source.
- `.env.example` must be kept up to date with every new environment variable
  the app needs (with a placeholder value), so the file itself stays
  trackable — check `.gitignore`'s `.env.*` / `!.env.example` rule still
  matches if you rename it.

## LLM / translation feature
- LLM calls go through OpenRouter using the OpenAI Python SDK pointed at
  `https://openrouter.ai/api/v1` (see `src/services/translation_service.py`
  and the standalone `translator.py` exercise script).
- System prompts for LLM features live as markdown files under `prompts/`,
  not inline in Python strings, so they're easy to review/tweak.
- Ask the LLM for JSON output explicitly in the prompt, and defensively
  parse the response (strip markdown code fences, validate expected keys)
  since not all models honor `response_format` strictly.
- LLMs' training data can be stale re: library APIs — verify any suggested
  package name/version actually exists (e.g. the exercise's suggested
  `dotenv==0.9.9` doesn't do what you'd expect; the correct package is
  `python-dotenv`). Don't trust a generated `requirements.txt` blindly.

## Git workflow used in this exercise
- Feature/bugfix work happens on the `Dev` branch, never directly on `main`.
- Commit messages follow Conventional Commits style seen in history
  (`fix: ...`, `feat: ...`).
- Open a PR from `Dev` into `main` for review before merging.

## Testing changes
- There's no automated test suite yet. After any change, manually verify by
  running `python src/main.py` and exercising the affected UI/endpoint
  (e.g. with `curl`) before committing.
