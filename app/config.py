from __future__ import annotations

import os


class Settings:
    ollama_host: str = os.environ.get("OLLAMA_HOST", "http://ollama:11434")
    llm_model: str = os.environ.get("LLM_MODEL", "gemma4:latest")
    llm_temperature: float = float(os.environ.get("LLM_TEMPERATURE", "0.2"))
    llm_num_ctx: int = int(os.environ.get("LLM_NUM_CTX", "8192"))

    tei_url: str = os.environ.get("TEI_URL", "http://tei:80")
    embedding_dim: int = int(os.environ.get("EMBEDDING_DIM", "1024"))

    qdrant_url: str = os.environ.get("QDRANT_URL", "http://qdrant:6333")
    qdrant_collection: str = os.environ.get("QDRANT_COLLECTION", "rinri_books")

    rag_top_k: int = int(os.environ.get("RAG_TOP_K", "6"))

    api_host: str = os.environ.get("API_HOST", "0.0.0.0")
    api_port: int = int(os.environ.get("API_PORT", "8000"))


settings = Settings()
