from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import yaml


# Candidate encodings to try, in priority order. Covers UTF-8 (with/without BOM),
# Windows-Japanese (CP932 is a superset of Shift_JIS), classic Shift_JIS, EUC-JP,
# and UTF-16 (which is common when a .txt is saved from Windows Notepad).
_ENCODINGS = ("utf-8-sig", "utf-8", "cp932", "shift_jis", "euc-jp", "utf-16")


@dataclass
class Document:
    source: str
    text: str
    metadata: dict = field(default_factory=dict)


def _read_text(path: Path) -> str:
    raw = path.read_bytes()
    for enc in _ENCODINGS:
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    # Last resort: keep going with replacement characters rather than crashing.
    return raw.decode("utf-8", errors="replace")


def _split_frontmatter(text: str) -> tuple[dict, str]:
    """Split optional YAML frontmatter from body.

    Recognises a leading `---\\n ... \\n---\\n` block. If absent or malformed,
    returns ({}, text).
    """
    if not text.startswith("---\n") and not text.startswith("---\r\n"):
        return {}, text
    # Find the closing fence on its own line.
    body_lines = text.splitlines()
    if not body_lines or body_lines[0] != "---":
        return {}, text
    end = -1
    for i in range(1, len(body_lines)):
        if body_lines[i] == "---":
            end = i
            break
    if end < 0:
        return {}, text
    front_str = "\n".join(body_lines[1:end])
    body = "\n".join(body_lines[end + 1 :]).lstrip("\n")
    try:
        meta = yaml.safe_load(front_str) or {}
        if not isinstance(meta, dict):
            meta = {}
    except yaml.YAMLError:
        meta = {}
    return meta, body


def load_txt_files(books_dir: Path) -> Iterator[Document]:
    for path in sorted(books_dir.rglob("*.txt")):
        text = _read_text(path)
        if not text.strip():
            continue
        meta, body = _split_frontmatter(text)
        if not body.strip():
            continue
        yield Document(
            source=str(path.relative_to(books_dir)),
            text=body,
            metadata=meta,
        )
