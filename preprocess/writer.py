"""Write cleaned chapters to data/cleaned/<title>/<NN>_<chapter>.txt with YAML frontmatter."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from preprocess.metadata import BookMetadata
from preprocess.splitter import Chapter


_INVALID_FS = re.compile(r'[\\/:*?"<>|\0]')
_REPEATED_UNDERSCORE = re.compile(r"_+")


def sanitize_filename(name: str, max_len: int = 60) -> str:
    s = _INVALID_FS.sub("_", name)
    s = s.replace(" ", "_").strip("._ ")
    s = _REPEATED_UNDERSCORE.sub("_", s)
    if not s:
        s = "untitled"
    return s[:max_len]


def write_chapter(
    out_root: Path,
    meta: BookMetadata,
    chapter: Chapter,
) -> Path:
    book_dir = out_root / sanitize_filename(meta.title)
    book_dir.mkdir(parents=True, exist_ok=True)

    fname = f"{chapter.index:02d}_{sanitize_filename(chapter.title)}.txt"
    out_path = book_dir / fname

    front: dict = {
        "title": meta.title,
        "author": meta.author,
        "publisher": meta.publisher,
        "year": meta.year,
        "chapter_index": chapter.index,
        "chapter_title": chapter.title,
        "source_file": meta.source_file,
    }
    front_yaml = yaml.safe_dump(
        front, allow_unicode=True, sort_keys=False, default_flow_style=False
    ).strip()

    body = chapter.text.strip()
    out_path.write_text(
        f"---\n{front_yaml}\n---\n\n{body}\n",
        encoding="utf-8",
    )
    return out_path
