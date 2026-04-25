"""Extract book-level metadata (title / author / publisher / year).

Strategy:
1. Honor a structured filename like "{書名}_{著者}.txt" or "{書名}_{著者}_{年}.txt"
2. Otherwise, ask the LLM to extract from the opening of the text. The LLM
   is only allowed to *report* what it sees, never to rewrite the text itself.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from preprocess.llm import chat_json, LLMError


META_SYSTEM_PROMPT = """\
あなたは日本語書籍の冒頭部から書誌情報(メタデータ)を抽出するアシスタントです。
原文に書かれている事実だけを報告してください。

【出力】
JSON オブジェクトのみ。次のキーを必ず含めてください:
- title (string | null) … 書籍のタイトル
- author (string | null) … 著者名(複数なら一人目の主著者)
- publisher (string | null) … 出版社名
- year (integer | null) … 発行年(西暦4桁)

判別できないキーは null にしてください。前後に説明文を付けず、JSON のみ返します。
"""


def _build_meta_user_prompt(text_head: str) -> str:
    return f"""\
以下は書籍の冒頭部です。書誌情報を抽出してください。

【書籍冒頭】
{text_head}
"""


@dataclass
class BookMetadata:
    title: str
    author: str | None = None
    publisher: str | None = None
    year: int | None = None
    source_file: str = ""


_FILENAME_SPLIT = re.compile(r"[_\-]")


def _try_int(value: str | None) -> int | None:
    if value is None:
        return None
    s = value.strip()
    if not s.isdigit():
        return None
    n = int(s)
    return n if 1500 <= n <= 2100 else None


def from_filename(filename: str) -> BookMetadata | None:
    """Parse 書名_著者[_年].txt style names. Return None if it doesn't fit."""
    stem = Path(filename).stem.strip()
    if not stem:
        return None
    parts = [p.strip() for p in _FILENAME_SPLIT.split(stem) if p.strip()]
    if not parts:
        return None
    title = parts[0]
    author = parts[1] if len(parts) >= 2 else None
    year = _try_int(parts[2]) if len(parts) >= 3 else None
    # Require a non-trivial title length to consider this "structured".
    # If the stem is something like "book01" we'll fall back to LLM.
    if len(title) < 2 or re.fullmatch(r"[A-Za-z0-9]+", title):
        return None
    return BookMetadata(title=title, author=author, year=year, source_file=filename)


def from_content(text: str, source_file: str, head_chars: int = 3000) -> BookMetadata:
    head = text[:head_chars]
    try:
        data = chat_json(META_SYSTEM_PROMPT, _build_meta_user_prompt(head))
    except LLMError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    return BookMetadata(
        title=(data.get("title") or Path(source_file).stem) if isinstance(data.get("title"), str) or data.get("title") is None else Path(source_file).stem,
        author=data.get("author") if isinstance(data.get("author"), str) else None,
        publisher=data.get("publisher") if isinstance(data.get("publisher"), str) else None,
        year=data.get("year") if isinstance(data.get("year"), int) else None,
        source_file=source_file,
    )


def extract_metadata(text: str, source_file: str) -> BookMetadata:
    """Top-level: prefer filename, fall back to LLM extraction."""
    from_name = from_filename(source_file)
    if from_name and from_name.title:
        return from_name
    return from_content(text, source_file=source_file)
