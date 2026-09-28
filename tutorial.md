# How `translator.py` works

`translator.py` is a small command-line tool that translates whatever text
you give it into a target language, using a large language model (LLM)
served through [OpenRouter](https://openrouter.ai).

## 1. Reading configuration from `.env`

```python
from dotenv import load_dotenv
load_dotenv()
```

`load_dotenv()` reads a `.env` file in the project root and copies its
key/value pairs into the process environment (`os.environ`). This is how the
program gets its secrets and settings without hard-coding them in the source
file:

- `OPENROUTER_API_KEY` — your personal API key from https://openrouter.ai/keys
- `TRANSLATE_MODEL` — which model to call (defaults to a free-tier model)
- `TARGET_LANGUAGE` — optional override for the translation target

Because `.env` is listed in `.gitignore`, your API key never gets committed
to git. `.env.example` documents which variables are expected, with
placeholder values, so anyone cloning the repo knows what to set up.

## 2. Talking to the LLM

```python
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=api_key,
)
```

OpenRouter exposes an API that is compatible with the OpenAI Python SDK. By
pointing the SDK's `base_url` at OpenRouter instead of OpenAI, the exact same
`client.chat.completions.create(...)` call now runs against whichever model
you choose from OpenRouter's catalog (`MODEL`, e.g.
`nvidia/nemotron-3.5-lightning:free`) — no other code changes needed.

## 3. The system prompt

```python
system_prompt = (
    "You are a professional translator. Translate the user's message into "
    f"{TARGET_LANGUAGE}. ..."
)
```

A "system prompt" tells the model what role to play and how to behave for
the whole conversation, as opposed to the "user prompt", which is the actual
content to act on. Here the system prompt fixes the model's role
("professional translator") and its target language, and explicitly asks for
just the translated text with no extra commentary — this keeps the output
clean and predictable for a CLI tool (or, later, for a JSON API response).

## 4. `llm_generate()`

```python
def llm_generate(user_prompt: str) -> str:
    ...
    completion = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return completion.choices[0].message.content
```

This is the reusable core function: given a piece of text (`user_prompt`),
it sends a two-message conversation (system + user) to the model and returns
the model's reply as plain text. Because it only depends on its input string
and environment variables, this function can be imported and reused
elsewhere in the app (e.g. in the note-taking app's translation feature)
instead of just from the command line.

## 5. The command-line entry point

```python
def main() -> None:
    if len(sys.argv) < 2:
        print('Usage: python translator.py "text to translate"')
        sys.exit(1)
    user_prompt = " ".join(sys.argv[1:])
    translation = llm_generate(user_prompt)
    print(translation)
```

`sys.argv` holds the command-line arguments; `sys.argv[0]` is the script
name itself, so `sys.argv[1:]` are the words the user typed after
`translator.py`. They're joined back into a single string so a quoted
sentence or several separate words both work, e.g.:

```bash
python translator.py "How are you?"
python translator.py How are you?
```

Any error (missing API key, network failure, bad model name, etc.) is
caught and printed as a friendly `Error: ...` message instead of a raw
Python traceback, then the script exits with a non-zero status code so
shell scripts can detect the failure.

## Note on the sample dependency versions

The original exercise prompt suggested `dotenv==0.9.9` in
`requirements.txt`. That package name is a red herring — it's an old,
unrelated PyPI package, not the `.env`-file loader used here. The correct
package is **`python-dotenv`** (imported as `from dotenv import
load_dotenv`), which is what `requirements.txt` actually installs. This is a
good real-world example of the "LLM limitations" warning from the slides:
always double-check that generated code references packages/APIs that
actually exist and do what you expect.
