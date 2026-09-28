"""Auto-generate a title and a few tags for a note from its content, via an
LLM served through OpenRouter. Used when a note is created with a blank
title, so the user isn't left staring at "Untitled".

Shares the same OpenRouter/OpenAI-SDK approach as translation_service.py;
kept as its own small module rather than a shared abstraction, matching the
rest of this app's one-file-per-feature service style.
"""

import json
import os
from pathlib import Path

from openai import OpenAI

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
PROMPT_PATH = ROOT_DIR / "prompts" / "auto_title_prompt.md"

MAX_TAGS = 3


class NoteAIError(Exception):
    """Raised when a title/tags suggestion could not be generated."""


def _load_system_prompt() -> str:
    template = PROMPT_PATH.read_text(encoding="utf-8")
    # The prompt file is markdown documentation with a fenced JSON example;
    # only the section after the "---" separator is the actual prompt text.
    return template.split("---", 1)[-1].strip()


def _get_client() -> OpenAI:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key or api_key == "your_openrouter_api_key_here":
        raise NoteAIError("OPENROUTER_API_KEY is not configured.")
    return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)


def generate_title_and_tags(content: str) -> dict:
    """Generate {"title": str, "tags": [str, ...]} from `content`.

    Raises NoteAIError on any failure (missing key, bad response, ...) -
    callers should treat this as best-effort and fall back to "Untitled".
    """
    model = os.getenv("TRANSLATE_MODEL", "nvidia/nemotron-3.5-lightning:free")

    client = _get_client()
    messages = [
        {"role": "system", "content": _load_system_prompt()},
        {"role": "user", "content": content},
    ]

    try:
        completion = client.chat.completions.create(
            model=model, messages=messages, response_format={"type": "json_object"}
        )
        raw = completion.choices[0].message.content
    except Exception:
        try:
            completion = client.chat.completions.create(model=model, messages=messages)
            raw = completion.choices[0].message.content
        except Exception as exc:
            raise NoteAIError(f"LLM request failed: {exc}") from exc

    cleaned = (raw or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    try:
        result = json.loads(cleaned)
    except (TypeError, json.JSONDecodeError) as exc:
        raise NoteAIError(f"LLM did not return valid JSON: {exc}. Raw: {raw!r}") from exc

    title = (result.get("title") or "").strip()
    if not title:
        raise NoteAIError(f"LLM response missing a usable title: {result!r}")

    tags = result.get("tags") or []
    if not isinstance(tags, list):
        tags = []
    tags = [str(t).strip() for t in tags if str(t).strip()][:MAX_TAGS]

    return {"title": title, "tags": tags}
