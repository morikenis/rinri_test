from __future__ import annotations

from typing import AsyncIterator, List

import httpx
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from app.config import settings


_qdrant: QdrantClient | None = None


def qdrant() -> QdrantClient:
    global _qdrant
    if _qdrant is None:
        _qdrant = QdrantClient(url=settings.qdrant_url)
    return _qdrant


async def embed(texts: List[str]) -> List[List[float]]:
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{settings.tei_url}/embed",
            json={"inputs": texts, "normalize": True, "truncate": True},
        )
        resp.raise_for_status()
        return resp.json()


async def search(query_vec: List[float], top_k: int) -> List[qm.ScoredPoint]:
    return qdrant().search(
        collection_name=settings.qdrant_collection,
        query_vector=query_vec,
        limit=top_k,
        with_payload=True,
    )


async def ollama_chat_stream(messages: list[dict]) -> AsyncIterator[str]:
    """Yield response chunks from Ollama's /api/chat streaming endpoint."""
    payload = {
        "model": settings.llm_model,
        "messages": messages,
        "stream": True,
        "options": {
            "temperature": settings.llm_temperature,
            "num_ctx": settings.llm_num_ctx,
        },
    }
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream(
            "POST", f"{settings.ollama_host}/api/chat", json=payload
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line:
                    continue
                import json

                obj = json.loads(line)
                msg = obj.get("message") or {}
                content = msg.get("content")
                if content:
                    yield content
                if obj.get("done"):
                    break
