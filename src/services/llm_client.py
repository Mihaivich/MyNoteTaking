"""Shared OpenAI-SDK-compatible client for Google's Gemini API.

Switched from OpenRouter to Gemini directly (per user request: OpenRouter's
free-tier models were responding too slowly). Gemini exposes an
OpenAI-compatible endpoint, so this keeps using the same `openai` SDK -
only the base_url, API key, and model name changed. See:
https://ai.google.dev/gemini-api/docs/openai

Both translation_service.py and note_ai_service.py need the same
"call the model for a single JSON object" logic, so it lives here once
instead of being duplicated in each.
"""

import json
import os

from openai import OpenAI

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
# In testing, the lite model was both faster and more reliable under load
# than the full gemini-3.8-flash (~3s vs. 6-70s per call, some of which
# failed outright - looked like free-tier rate limiting).
DEFAULT_MODEL = "gemini-3.5-flash-lite"


class LLMError(Exception):
    """Raised when an LLM call or its JSON response could not be completed."""


def get_client() -> OpenAI:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key == "your_gemini_api_key_here":
        raise LLMError(
            "GEMINI_API_KEY is not configured. Set it in .env (locally) or "
            "as an environment variable (in production). Get a free key at "
            "https://aistudio.google.com/apikey"
        )
    return OpenAI(base_url=GEMINI_BASE_URL, api_key=api_key)


def get_model() -> str:
    return os.getenv("GEMINI_MODEL", DEFAULT_MODEL)


def call_for_json(system_prompt: str, user_prompt: str) -> dict:
    """Send a system+user message pair and parse a single JSON object out
    of the response. Raises LLMError on any failure (missing key, request
    error, or a response that isn't valid JSON).
    """
    client = get_client()
    model = get_model()
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
        # Fall back to a plain call and rely on the prompt's own
        # JSON-only instruction, in case response_format isn't honored.
        try:
            completion = client.chat.completions.create(model=model, messages=messages)
            raw = completion.choices[0].message.content
        except Exception as exc:
            raise LLMError(f"LLM request failed: {exc}") from exc

    cleaned = (raw or "").strip()
    if cleaned.startswith("```"):
        # Defensively strip a ```json ... ``` fence if the model added one
        # despite being asked not to.
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except (TypeError, json.JSONDecodeError) as exc:
        raise LLMError(
            f"LLM did not return valid JSON: {exc}. Raw response: {raw!r}"
        ) from exc
