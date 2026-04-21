"""Ingestion entry point.

Usage (inside the api container, or any env with deps installed):
    python -m ingest.ingest --books-dir data/books --recreate
"""
from __future__ import annotations

import argparse
import os
import sys
import uuid
from pathlib import Path
from typing import Iterable, List

import httpx
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from ingest.chunker import Chunk, chunk_text
from ingest.loader import Document, load_txt_files


TEI_URL = os.environ.get("TEI_URL", "http://tei:80")
QDRANT_URL = os.environ.get("QDRANT_URL", "http://qdrant:6333")
COLLECTION = os.environ.get("QDRANT_COLLECTION", "rinri_books")
EMBED_DIM = int(os.environ.get("EMBEDDING_DIM", "1024"))
CHUNK_SIZE = int(os.environ.get("RAG_CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(os.environ.get("RAG_CHUNK_OVERLAP", "120"))

EMBED_BATCH = 32


def ensure_collection(client: QdrantClient, recreate: bool) -> None:
    exists = client.collection_exists(COLLECTION)
    if exists and recreate:
        client.delete_collection(COLLECTION)
        exists = False
    if not exists:
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=qm.VectorParams(size=EMBED_DIM, distance=qm.Distance.COSINE),
        )


def embed_batch(texts: List[str]) -> List[List[float]]:
    # TEI OpenAI-compatible endpoint
    resp = httpx.post(
        f"{TEI_URL}/embed",
        json={"inputs": texts, "normalize": True, "truncate": True},
        timeout=120.0,
    )
    resp.raise_for_status()
    data = resp.json()
    # TEI /embed returns a list[list[float]]
    return data


def iter_chunks(docs: Iterable[Document]):
    for doc in docs:
        for ch in chunk_text(doc.text, CHUNK_SIZE, CHUNK_OVERLAP):
            yield doc, ch


def upsert(client: QdrantClient, doc_chunks, vectors) -> None:
    points = []
    for (doc, ch), vec in zip(doc_chunks, vectors):
        points.append(
            qm.PointStruct(
                id=str(uuid.uuid4()),
                vector=vec,
                payload={
                    "source": doc.source,
                    "chunk_index": ch.index,
                    "text": ch.text,
                },
            )
        )
    client.upsert(collection_name=COLLECTION, points=points, wait=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--books-dir", default="data/books")
    parser.add_argument("--recreate", action="store_true", help="drop & recreate collection")
    args = parser.parse_args()

    books_dir = Path(args.books_dir).resolve()
    if not books_dir.exists():
        print(f"books dir not found: {books_dir}", file=sys.stderr)
        return 1

    client = QdrantClient(url=QDRANT_URL)
    ensure_collection(client, recreate=args.recreate)

    docs = list(load_txt_files(books_dir))
    if not docs:
        print(f"no .txt files found under {books_dir}", file=sys.stderr)
        return 1
    print(f"loaded {len(docs)} document(s)")

    batch_doc_chunks = []
    batch_texts: List[str] = []
    total = 0

    def flush():
        nonlocal batch_doc_chunks, batch_texts, total
        if not batch_texts:
            return
        vectors = embed_batch(batch_texts)
        upsert(client, batch_doc_chunks, vectors)
        total += len(batch_texts)
        print(f"  upserted: {total} chunks")
        batch_doc_chunks = []
        batch_texts = []

    for doc, ch in iter_chunks(docs):
        batch_doc_chunks.append((doc, ch))
        batch_texts.append(ch.text)
        if len(batch_texts) >= EMBED_BATCH:
            flush()
    flush()

    print(f"done. total chunks indexed: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
