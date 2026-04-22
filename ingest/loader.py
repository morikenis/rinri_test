from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


# Candidate encodings to try, in priority order. Covers UTF-8 (with/without BOM),
# Windows-Japanese (CP932 is a superset of Shift_JIS), classic Shift_JIS, EUC-JP,
# and UTF-16 (which is common when a .txt is saved from Windows Notepad).
_ENCODINGS = ("utf-8-sig", "utf-8", "cp932", "shift_jis", "euc-jp", "utf-16")


@dataclass
class Document:
    source: str
    text: str


def _read_text(path: Path) -> str:
    raw = path.read_bytes()
    for enc in _ENCODINGS:
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    # Last resort: keep going with replacement characters rather than crashing.
    return raw.decode("utf-8", errors="replace")


def load_txt_files(books_dir: Path) -> Iterator[Document]:
    for path in sorted(books_dir.rglob("*.txt")):
        text = _read_text(path)
        if not text.strip():
            continue
        yield Document(source=str(path.relative_to(books_dir)), text=text)
