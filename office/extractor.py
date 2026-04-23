from __future__ import annotations

import json
import os

import httpx


OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://ollama:11434")
LLM_MODEL = os.environ.get("LLM_MODEL", "gemma4:latest")
LLM_NUM_CTX = int(os.environ.get("LLM_NUM_CTX", "8192"))


class ExtractorError(RuntimeError):
    pass


def extract_json(system_prompt: str, user_prompt: str, temperature: float = 0.1) -> dict:
    """Call Ollama with JSON-mode and return a parsed dict.

    Ollama's `format: "json"` option instructs the model to emit valid JSON,
    which Gemma 4 instruct follows reliably for short extraction tasks.
    """
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "format": "json",
        "options": {
            "temperature": temperature,
            "num_ctx": LLM_NUM_CTX,
        },
    }
    resp = httpx.post(
        f"{OLLAMA_HOST}/api/chat",
        json=payload,
        timeout=httpx.Timeout(connect=10.0, read=600.0, write=60.0, pool=10.0),
    )
    resp.raise_for_status()
    data = resp.json()
    content = (data.get("message") or {}).get("content", "").strip()
    if not content:
        raise ExtractorError("LLM returned empty content")

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # Salvage: strip everything outside the outermost { ... } block.
        start = content.find("{")
        end = content.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(content[start : end + 1])
            except json.JSONDecodeError as inner:
                raise ExtractorError(
                    f"LLM did not return valid JSON: {content[:200]}"
                ) from inner
        raise ExtractorError(f"LLM did not return valid JSON: {content[:200]}")
