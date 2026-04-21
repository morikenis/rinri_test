from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List


_SENT_SPLIT = re.compile(r"(?<=[。！？\!\?])\s*|\n{2,}")


@dataclass
class Chunk:
    text: str
    index: int


def _split_sentences(text: str) -> List[str]:
    parts = [p.strip() for p in _SENT_SPLIT.split(text) if p and p.strip()]
    return parts


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 120) -> List[Chunk]:
    """Split Japanese text on sentence boundaries, packing up to chunk_size chars.

    Overlap is applied by re-emitting the tail sentences of the previous chunk
    up to `overlap` characters, which preserves context across chunk boundaries
    without breaking sentences mid-way.
    """
    sentences = _split_sentences(text)
    chunks: List[Chunk] = []
    buf: List[str] = []
    buf_len = 0
    idx = 0

    def flush() -> None:
        nonlocal buf, buf_len, idx
        if not buf:
            return
        joined = "".join(buf).strip()
        if joined:
            chunks.append(Chunk(text=joined, index=idx))
            idx += 1

    for sent in sentences:
        if buf_len + len(sent) > chunk_size and buf:
            flush()
            # carry overlap from the tail of the previous buffer
            tail: List[str] = []
            tail_len = 0
            for s in reversed(buf):
                if tail_len + len(s) > overlap:
                    break
                tail.append(s)
                tail_len += len(s)
            buf = list(reversed(tail))
            buf_len = sum(len(s) for s in buf)
        buf.append(sent)
        buf_len += len(sent)

    flush()
    return chunks
