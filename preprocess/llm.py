"""Minimal Ollama JSON-mode client for the preprocessing pipeline."""
from __future__ import annotations

import json
import os
from typing import Any

import httpx


OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://ollama:11434")
LLM_MODEL = os.environ.get("LLM_MODEL", "gemma4:latest")
LLM_NUM_CTX = int(os.environ.get("LLM_NUM_CTX", "8192"))


class LLMError(RuntimeError):
    pass


def chat_json(
    system_prompt: str,
    user_prompt: str,
    *,
    temperature: float = 0.1,
    timeout_s: float = 600.0,
) -> Any:
    """Call Ollama in JSON mode and return the parsed object (dict or list)."""
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
        timeout=httpx.Timeout(connect=10.0, read=timeout_s, write=60.0, pool=10.0),
    )
    resp.raise_for_status()
    data = resp.json()
    content = (data.get("message") or {}).get("content", "").strip()
    if not content:
        raise LLMError("LLM returned empty content")

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # Salvage: extract the first {...} or [...] block.
        for opener, closer in (("{", "}"), ("[", "]")):
            start = content.find(opener)
            end = content.rfind(closer)
            if 0 <= start < end:
                try:
                    return json.loads(content[start : end + 1])
                except json.JSONDecodeError:
                    continue
        raise LLMError(f"LLM did not return valid JSON: {content[:200]}")
