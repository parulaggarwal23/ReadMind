"""One interface over several LLM providers: gemini | openai | ollama | mock.
`mock` needs no API key and is used by tests/CI."""
import json
import re
import time
from functools import lru_cache

import requests

from config import GEMINI_API_KEY, LLM_MODEL, LLM_PROVIDER, OLLAMA_URL, OPENAI_API_KEY


@lru_cache(maxsize=1)
def _gemini():
    from google import genai
    return genai.Client(api_key=GEMINI_API_KEY or None)


@lru_cache(maxsize=1)
def _openai():
    from openai import OpenAI
    return OpenAI(api_key=OPENAI_API_KEY or None)


def _call(provider, model, system, prompt, temperature, json_mode):
    if provider == "gemini":
        from google.genai import types
        cfg = {"system_instruction": system, "temperature": temperature}
        if json_mode:
            cfg["response_mime_type"] = "application/json"
        resp = _gemini().models.generate_content(model=model, contents=prompt,
                                                 config=types.GenerateContentConfig(**cfg))
        return resp.text or ""
    if provider == "openai":
        kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}
        resp = _openai().chat.completions.create(
            model=model, temperature=temperature,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}], **kwargs)
        return resp.choices[0].message.content or ""
    if provider == "ollama":
        body = {"model": model, "stream": False, "options": {"temperature": temperature},
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]}
        if json_mode:
            body["format"] = "json"
        r = requests.post(f"{OLLAMA_URL}/api/chat", json=body, timeout=300)
        r.raise_for_status()
        return r.json()["message"]["content"]
    if provider == "mock":
        return _mock(prompt, json_mode)
    raise ValueError(f"Unknown LLM provider '{provider}'")


def _mock(prompt, json_mode):
    if json_mode:
        return json.dumps({"accuracy": 3, "relevance": 3, "key_points_covered": [True, False],
                           "claims_total": 2, "claims_unsupported": 1, "rationale": "mock judge",
                           "question": "Why was this changed?", "category": "rationale",
                           "reference_answer": "mock", "key_points": ["mock point"]})
    ids = re.findall(r"^\[((?:code|commit|issue|pr|review|doc):[^\]]+)\]", prompt, re.M)
    if not ids:
        return "I am not certain about the history of this code without more information."
    return (f"The most relevant evidence is {ids[0]} [{ids[0]}]. "
            f"Related context appears in [{ids[min(1, len(ids) - 1)]}].\n\nRecommendation: review the cited history first.")


def generate(system: str, prompt: str, provider: str | None = None, model: str | None = None,
             temperature: float = 0.0, json_mode: bool = False, retries: int = 3) -> str:
    provider, model = provider or LLM_PROVIDER, model or LLM_MODEL
    for attempt in range(retries):
        try:
            return _call(provider, model, system, prompt, temperature, json_mode)
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** (attempt + 1))
    return ""


def parse_json(text: str) -> dict:
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        return json.loads(m.group(0)) if m else {}
