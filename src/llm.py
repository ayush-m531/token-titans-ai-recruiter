"""llm.py - the only file that talks to Gemini.
ask_llm(rules, text, check) -> (result, model_name) or (None, "all models failed")
- rules go as system instruction, text as the message (kept separate)
- bad JSON  -> retry the SAME model once with the error
- busy/timeout/any API error -> go to the NEXT model
"""
import os
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
MODELS = ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.7-flash"]

client = genai.Client(
    api_key=os.environ.get("GEMINI_API_KEY"),
    http_options=types.HttpOptions(
        timeout=15000,                                    # 15 s per call
        retry_options=types.HttpRetryOptions(attempts=1),  # no hidden SDK retries
    ),
)


def _call(model, rules, text):
    r = client.models.generate_content(
        model=model,
        contents=text,
        config=types.GenerateContentConfig(
            system_instruction=rules,
            temperature=0,
            response_mime_type="application/json",
        ),
    )
    return r.text or ""


def ask_llm(rules, text, check):
    """check(raw_text) must return (result, None) if ok, or (None, error_message)."""
    for model in MODELS:
        prompt = text
        for attempt in (1, 2):                       # 2nd attempt only for bad JSON
            start = time.time()
            try:
                raw = _call(model, rules, prompt)
            except Exception as e:                    # busy, timeout, network -> next model
                print(f"[llm] {model} try {attempt}: FAIL ({type(e).__name__}) {time.time()-start:.1f}s")
                break
            result, error = check(raw)
            if error is None:
                print(f"[llm] {model} try {attempt}: OK {time.time()-start:.1f}s")
                return result, model
            print(f"[llm] {model} try {attempt}: BAD JSON {time.time()-start:.1f}s -> {error[:80]}")
            prompt = (text + "\n\nYour previous JSON was invalid: " + error
                      + "\nReturn the corrected JSON only.")
    return None, "all models failed"


if __name__ == "__main__":
    import json

    def check_ok(raw):
        try:
            data = json.loads(raw)
            return (data, None) if data.get("ok") is True else (None, 'expected {"ok": true}')
        except json.JSONDecodeError as e:
            return None, f"not valid JSON: {e}"

    print(ask_llm('Reply only with JSON: {"ok": true}', "test", check_ok))
