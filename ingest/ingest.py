"""Ingestion entry point.

Usage (inside the api container, or any env with deps installed):
    python -m ingest.ingest --books-dir /srv/data/cleaned --recreate

The loader recognises optional YAML frontmatter at the top of each .txt
(emitted by `python -m preprocess.run`). When present, fields like title /
author / chapter_title are stored as Qdrant payload and used to build a
short prefix that is *prepended to chunks at embedding time only* — so the
retrieval signal includes book/chapter context, while the stored chunk
text remains the original prose for clean citation display.
"""
from __future__ import annotations

import argparse
import os
import sys
import uuid
from pathlib import Path
from typing import Iterable, List, Tuple

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

EMBED_BATCH = 16


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
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            resp = httpx.post(
                f"{TEI_URL}/embed",
                json={"inputs": texts, "normalize": True, "truncate": True},
                timeout=httpx.Timeout(connect=10.0, read=600.0, write=60.0, pool=10.0),
            )
            resp.raise_for_status()
            return resp.json()
        except (httpx.ReadTimeout, httpx.ConnectError, httpx.RemoteProtocolError) as e:
            last_err = e
            print(f"  [retry {attempt + 1}/3] embed failed: {type(e).__name__}")
    assert last_err is not None
    raise last_err


def _build_prefix(meta: dict) -> str:
    title = (meta.get("title") or "").strip()
    chapter = (meta.get("chapter_title") or "").strip()
    if title and chapter:
        return f"【{title} / {chapter}】\n"
    if title:
        return f"【{title}】\n"
    return ""


def iter_chunks(docs: Iterable[Document]):
    for doc in docs:
        prefix = _build_prefix(doc.metadata)
        for ch in chunk_text(doc.text, CHUNK_SIZE, CHUNK_OVERLAP):
            yield doc, ch, prefix


def upsert(
    client: QdrantClient,
    doc_chunks: List[Tuple[Document, Chunk, str]],
    vectors,
) -> None:
    points = []
    for (doc, ch, _prefix), vec in zip(doc_chunks, vectors):
        meta = doc.metadata or {}
        payload = {
            "source": doc.source,
            "chunk_index": ch.index,
            "text": ch.text,
            "title": meta.get("title"),
            "author": meta.get("author"),
            "publisher": meta.get("publisher"),
            "year": meta.get("year"),
            "chapter_index": meta.get("chapter_index"),
            "chapter_title": meta.get("chapter_title"),
            "source_file": meta.get("source_file"),
        }
        points.append(
            qm.PointStruct(id=str(uuid.uuid4()), vector=vec, payload=payload)
        )
    client.upsert(collection_name=COLLECTION, points=points, wait=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--books-dir", default="data/cleaned")
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

    batch_doc_chunks: List[Tuple[Document, Chunk, str]] = []
    batch_texts: List[str] = []  # the texts actually sent to the embedder (with prefix)
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

    for doc, ch, prefix in iter_chunks(docs):
        batch_doc_chunks.append((doc, ch, prefix))
        batch_texts.append(prefix + ch.text)
        if len(batch_texts) >= EMBED_BATCH:
            flush()
    flush()

    print(f"done. total chunks indexed: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
