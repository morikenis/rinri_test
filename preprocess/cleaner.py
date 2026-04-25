"""Deterministic text cleanup. No LLM, no rewriting of meaning.

Only safe transforms:
- Unicode NFKC normalization (full-width digits/letters → half-width, etc.)
- Strip BOM and zero-width characters
- Normalize line endings to \n
- Collapse runs of horizontal whitespace within a line to a single space
- Drop common page-number patterns when they occupy a whole line
- Collapse 3+ consecutive blank lines to 2
"""
from __future__ import annotations

import re
import unicodedata


_PAGE_PATTERNS = [
    re.compile(r"^[─━─—\-=]{1,3}\s*\d{1,5}\s*[─━─—\-=]{1,3}$"),  # ─ 12 ─
    re.compile(r"^-\s*\d{1,5}\s*-$"),                              # - 12 -
    re.compile(r"^\d{1,5}\s*/\s*\d{1,5}$"),                        # 12/345
    re.compile(r"^p\.?\s*\d{1,5}$", re.IGNORECASE),                # p.12 / page 12
    re.compile(r"^page\s+\d{1,5}$", re.IGNORECASE),
    re.compile(r"^[\(（]\s*\d{1,5}\s*[\)）]$"),                    # (12)
]

_HORIZONTAL_WS = re.compile(r"[ \t　 ]+")
_BLANK_RUN = re.compile(r"\n{3,}")


def _is_page_number_line(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    return any(pat.match(s) for pat in _PAGE_PATTERNS)


def clean_text(text: str) -> str:
    # Strip BOM and zero-width
    text = text.replace("﻿", "").replace("​", "").replace("‌", "")

    # Unicode NFKC: 全角→半角の英数字記号など。日本語仮名漢字には影響しない。
    text = unicodedata.normalize("NFKC", text)

    # Normalize newlines
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    cleaned_lines: list[str] = []
    for line in text.split("\n"):
        # Collapse horizontal whitespace within the line
        line = _HORIZONTAL_WS.sub(" ", line)
        line = line.strip()
        if _is_page_number_line(line):
            continue
        cleaned_lines.append(line)

    text = "\n".join(cleaned_lines)
    text = _BLANK_RUN.sub("\n\n", text)
    return text.strip() + "\n"
