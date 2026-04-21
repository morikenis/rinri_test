from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


@dataclass
class Document:
    source: str
    text: str


def load_txt_files(books_dir: Path) -> Iterator[Document]:
    for path in sorted(books_dir.rglob("*.txt")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if not text.strip():
            continue
        yield Document(source=str(path.relative_to(books_dir)), text=text)
