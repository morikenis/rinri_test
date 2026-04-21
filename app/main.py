from __future__ import annotations

import json
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.config import settings
from app.rag import answer_stream


app = FastAPI(title="Rinri RAG API")


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    question: str
    history: Optional[list[ChatMessage]] = None


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "model": settings.llm_model}


@app.post("/chat")
async def chat(req: ChatRequest) -> StreamingResponse:
    history = [m.model_dump() for m in (req.history or [])]

    async def event_gen():
        async for event in answer_stream(req.question, history=history):
            yield json.dumps(event, ensure_ascii=False) + "\n"

    return StreamingResponse(event_gen(), media_type="application/x-ndjson")
