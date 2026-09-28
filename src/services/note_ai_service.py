"""Auto-generate a title and a few tags for a note from its content, via an
LLM (Google's Gemini API - see src/services/llm_client.py for why/how).
Used when a note is created with a blank title, so the user isn't left
staring at "Untitled".
"""

from pathlib import Path

from src.services.llm_client import LLMError, call_for_json

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
PROMPT_PATH = ROOT_DIR / "prompts" / "auto_title_prompt.md"

MAX_TAGS = 3


class NoteAIError(LLMError):
    """Raised when a title/tags suggestion could not be generated."""


def _load_system_prompt() -> str:
    template = PROMPT_PATH.read_text(encoding="utf-8")
    # The prompt file is markdown documentation with a fenced JSON example;
    # only the section after the "---" separator is the actual prompt text.
    return template.split("---", 1)[-1].strip()


def generate_title_and_tags(content: str) -> dict:
    """Generate {"title": str, "tags": [str, ...]} from `content`.

    Raises NoteAIError on any failure (missing key, bad response, ...) -
    callers should treat this as best-effort and fall back to "Untitled".
    """
    try:
        result = call_for_json(_load_system_prompt(), content)
    except LLMError as exc:
        raise NoteAIError(str(exc)) from exc

    title = (result.get("title") or "").strip()
    if not title:
        raise NoteAIError(f"LLM response missing a usable title: {result!r}")

    tags = result.get("tags") or []
    if not isinstance(tags, list):
        tags = []
    tags = [str(t).strip() for t in tags if str(t).strip()][:MAX_TAGS]

    return {"title": title, "tags": tags}
