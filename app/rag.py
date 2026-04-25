from __future__ import annotations

from typing import AsyncIterator, List

from qdrant_client.http import models as qm

from app.clients import embed, ollama_chat_stream, search
from app.config import settings
from app.prompts import SYSTEM_PROMPT, build_context, build_user_message


async def retrieve(question: str, top_k: int | None = None) -> List[qm.ScoredPoint]:
    k = top_k or settings.rag_top_k
    vecs = await embed([question])
    return await search(vecs[0], k)


async def answer_stream(
    question: str, history: list[dict] | None = None
) -> AsyncIterator[dict]:
    """Stream answer chunks.

    Emits dicts:
      {"type": "sources", "items": [{"source": str, "chunk_index": int, "score": float, "text": str}]}
      {"type": "delta", "text": str}
      {"type": "done"}
    """
    hits = await retrieve(question)
    sources_payload = [
        {
            "source": (h.payload or {}).get("source", ""),
            "chunk_index": (h.payload or {}).get("chunk_index", 0),
            "score": float(h.score),
            "text": (h.payload or {}).get("text", ""),
            "title": (h.payload or {}).get("title"),
            "author": (h.payload or {}).get("author"),
            "chapter_title": (h.payload or {}).get("chapter_title"),
        }
        for h in hits
    ]
    yield {"type": "sources", "items": sources_payload}

    context = build_context(hits)
    user_msg = build_user_message(question, context)

    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_msg})

    async for delta in ollama_chat_stream(messages):
        yield {"type": "delta", "text": delta}

    yield {"type": "done"}
