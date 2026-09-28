"""Translate note titles/content using an LLM served through OpenRouter.

Reuses the same OpenAI-SDK-pointed-at-OpenRouter approach as the standalone
translator.py exercise script, but embedded as a reusable service for the
Flask app's /api/notes/<id>/translate endpoint. The system prompt lives in
prompts/translate_prompt.md so it can be tweaked without touching code.
"""

import json
import os
from pathlib import Path

from openai import OpenAI

# Repo root is two levels up from src/services/
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
PROMPT_PATH = ROOT_DIR / "prompts" / "translate_prompt.md"

DEFAULT_TARGET_LANGUAGE = "Chinese (Simplified)"


class TranslationError(Exception):
    """Raised when a note could not be translated."""


def _load_system_prompt(target_language: str) -> str:
    template = PROMPT_PATH.read_text(encoding="utf-8")
    # The prompt file is markdown documentation with a fenced JSON example;
    # only the section after the "---" separator is the actual prompt text.
    prompt_body = template.split("---", 1)[-1].strip()
    return prompt_body.format(target_language=target_language)


def _get_client() -> OpenAI:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key or api_key == "your_openrouter_api_key_here":
        raise TranslationError(
            "OPENROUTER_API_KEY is not configured. Set it in .env (locally) "
            "or as an environment variable (in production)."
        )
    return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)


def translate_note(title: str, content: str, target_language: str = None) -> dict:
    """Translate a note's title/content into `target_language`.

    Returns a dict: {translated_title, translated_content, target_language}.
    Raises TranslationError on any failure (missing key, bad response, ...).
    """
    target_language = target_language or DEFAULT_TARGET_LANGUAGE
    model = os.getenv("TRANSLATE_MODEL", "nvidia/nemotron-3.5-lightning:free")

    client = _get_client()
    system_prompt = _load_system_prompt(target_language)
    user_prompt = json.dumps({"title": title, "content": content}, ensure_ascii=False)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        # Ask for strict JSON output where the model supports it.
        completion = client.chat.completions.create(
            model=model, messages=messages, response_format={"type": "json_object"}
        )
        raw = completion.choices[0].message.content
    except Exception:
        # Not every model on OpenRouter honors response_format; fall back to
        # a plain call and rely on the prompt's own JSON-only instruction.
        try:
            completion = client.chat.completions.create(model=model, messages=messages)
            raw = completion.choices[0].message.content
        except Exception as exc:
            raise TranslationError(f"LLM request failed: {exc}") from exc

    cleaned = (raw or "").strip()
    if cleaned.startswith("```"):
        # Defensively strip a ```json ... ``` fence if the model added one
        # despite being asked not to.
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    try:
        result = json.loads(cleaned)
    except (TypeError, json.JSONDecodeError) as exc:
        raise TranslationError(
            f"LLM did not return valid JSON: {exc}. Raw response: {raw!r}"
        ) from exc

    for field in ("translated_title", "translated_content"):
        if field not in result:
            raise TranslationError(f"LLM response missing '{field}': {result!r}")

    result.setdefault("target_language", target_language)
    return result
