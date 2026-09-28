"""Translate note titles/content using an LLM (Google's Gemini API - see
src/services/llm_client.py for why/how). The system prompt lives in
prompts/translate_prompt.md so it can be tweaked without touching code.
"""

import json
from pathlib import Path

from src.services.llm_client import LLMError, call_for_json

# Repo root is two levels up from src/services/
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
PROMPT_PATH = ROOT_DIR / "prompts" / "translate_prompt.md"

DEFAULT_TARGET_LANGUAGE = "Chinese (Simplified)"


class TranslationError(LLMError):
    """Raised when a note could not be translated."""


def _load_system_prompt(target_language: str) -> str:
    template = PROMPT_PATH.read_text(encoding="utf-8")
    # The prompt file is markdown documentation with a fenced JSON example;
    # only the section after the "---" separator is the actual prompt text.
    prompt_body = template.split("---", 1)[-1].strip()
    return prompt_body.format(target_language=target_language)


def translate_note(title: str, content: str, target_language: str = None) -> dict:
    """Translate a note's title/content into `target_language`.

    Returns a dict: {translated_title, translated_content, target_language}.
    Raises TranslationError on any failure (missing key, bad response, ...).
    """
    target_language = target_language or DEFAULT_TARGET_LANGUAGE
    system_prompt = _load_system_prompt(target_language)
    user_prompt = json.dumps({"title": title, "content": content}, ensure_ascii=False)

    try:
        result = call_for_json(system_prompt, user_prompt)
    except LLMError as exc:
        raise TranslationError(str(exc)) from exc

    for field in ("translated_title", "translated_content"):
        if field not in result:
            raise TranslationError(f"LLM response missing '{field}': {result!r}")

    result.setdefault("target_language", target_language)
    return result
