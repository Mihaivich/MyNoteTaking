"""
translator.py

A small command-line translator built on top of an LLM served through
OpenRouter (using the OpenAI Python SDK as a drop-in client, per
https://openrouter.ai/docs/quickstart).

Usage:
    python translator.py "How are you?"

The API key is read from the .env file (OPENROUTER_API_KEY). The target
language is fixed by the TARGET_LANGUAGE constant below (default: Chinese
(Simplified)) but can also be overridden with the TARGET_LANGUAGE env var.
"""

import os
import sys

from dotenv import load_dotenv
from openai import OpenAI

# Load variables from a local .env file (OPENROUTER_API_KEY, TRANSLATE_MODEL, ...)
load_dotenv()

# Target language for the translation. Change this, or set the
# TARGET_LANGUAGE environment variable, to translate into a different language.
TARGET_LANGUAGE = os.getenv("TARGET_LANGUAGE", "Chinese (Simplified)")

# Any model slug from https://openrouter.ai/models works here.
MODEL = os.getenv("TRANSLATE_MODEL", "nvidia/nemotron-3.5-lightning:free")


def llm_generate(user_prompt: str) -> str:
    """Translate `user_prompt` into TARGET_LANGUAGE using an LLM via OpenRouter.

    Reads OPENROUTER_API_KEY from the environment (populated from .env).
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key or api_key == "your_openrouter_api_key_here":
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. Copy .env.example to .env and add "
            "your key from https://openrouter.ai/keys"
        )

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

    system_prompt = (
        "You are a professional translator. Translate the user's message into "
        f"{TARGET_LANGUAGE}. Preserve the original meaning, tone, and any "
        "formatting. Reply with ONLY the translated text - no explanations, "
        "no quotes, no extra commentary."
    )

    completion = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

    return completion.choices[0].message.content


def main() -> None:
    if len(sys.argv) < 2:
        print('Usage: python translator.py "text to translate"')
        sys.exit(1)

    user_prompt = " ".join(sys.argv[1:])

    try:
        translation = llm_generate(user_prompt)
    except Exception as exc:  # surfaced to the CLI user as a readable error
        print(f"Error: {exc}")
        sys.exit(1)

    print(translation)


if __name__ == "__main__":
    main()
