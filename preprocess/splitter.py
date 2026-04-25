"""Detect chapter boundaries and split text into chapters.

Body text is *never* rewritten. We only return positions and headings.

Pipeline:
1. Pattern-based detection (regex on line starts) — fast, deterministic.
2. If too few chapters were found, ask the LLM to suggest *additional regex
   patterns* it sees in a sample window. The LLM never returns text — only
   pattern strings. We then re-run regex with those patterns.
3. If still nothing, return the whole text as a single chapter.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from preprocess.llm import chat_json, LLMError


# Kanji digits used in chapter numbers
_KANJI_NUM = "〇零一二三四五六七八九十百千万"

# Default heading patterns. Each pattern matches the start of a line (after strip).
_DEFAULT_HEADING_PATTERNS: list[re.Pattern[str]] = [
    re.compile(rf"^第\s*[{_KANJI_NUM}\d]+\s*[章節編篇部]"),
    re.compile(rf"^[{_KANJI_NUM}\d]+\s*[章節編篇部](?!.*[、。])"),
    re.compile(r"^(?:序章|終章|序論|序説|序文|序|まえがき|前書き|はしがき|"
               r"はじめに|あとがき|後書き|付録|附録|結語|結論|跋|跋文|"
               r"凡例|目次|奥付)\b"),
    # Roman/Arabic numbered like "PART 1" or "Chapter 1"
    re.compile(r"^(?:Part|PART|Chapter|CHAPTER)\s+\d+", re.IGNORECASE),
]

# Heading lines should be short; reject false positives like full sentences.
_MAX_HEADING_LEN = 40


@dataclass
class Chapter:
    index: int
    title: str
    text: str


@dataclass
class Heading:
    offset: int  # absolute char offset in original text
    title: str


def _find_with_patterns(text: str, patterns: list[re.Pattern[str]]) -> list[Heading]:
    headings: list[Heading] = []
    pos = 0
    for line in text.split("\n"):
        stripped = line.strip()
        if 1 <= len(stripped) <= _MAX_HEADING_LEN:
            for pat in patterns:
                if pat.search(stripped):
                    headings.append(Heading(offset=pos, title=stripped))
                    break
        pos += len(line) + 1  # +1 for newline
    return headings


_LLM_SYS_PROMPT_PATTERNS = """\
あなたは日本語書籍の章構成パターンを判別するアシスタントです。
入力されたテキスト断片を読み、章・節の見出し行に該当する**書式パターン**を
正規表現として返してください。

【厳守】
- 本文は絶対に書き換えず、要約や言い換えもしない。
- 出力は JSON のみ。次の形式を厳守する。
  {"patterns": ["...", "..."]}
- patterns には、章見出し行の先頭にマッチする Python 正規表現を入れる。
  (例: "^第[一二三四五六七八九十百\\\\d]+章", "^その[一二三四五]")
- 章構造が見当たらないと判断した場合は空配列を返す。
"""


def _llm_pattern_suggestions(sample: str) -> list[re.Pattern[str]]:
    user_prompt = f"""\
【テキスト断片(冒頭〜章見出しが含まれる可能性のある領域)】
{sample}

このテキストに含まれる章・節の見出しパターンを正規表現で挙げてください。
"""
    try:
        data = chat_json(_LLM_SYS_PROMPT_PATTERNS, user_prompt, temperature=0.0)
    except LLMError:
        return []
    if not isinstance(data, dict):
        return []
    patterns_raw = data.get("patterns")
    if not isinstance(patterns_raw, list):
        return []
    compiled: list[re.Pattern[str]] = []
    for p in patterns_raw:
        if not isinstance(p, str) or not p.strip():
            continue
        try:
            compiled.append(re.compile(p))
        except re.error:
            continue
    return compiled


def find_chapter_headings(
    text: str,
    *,
    use_llm_fallback: bool = True,
) -> list[Heading]:
    headings = _find_with_patterns(text, _DEFAULT_HEADING_PATTERNS)
    if len(headings) >= 2:
        return headings

    if not use_llm_fallback:
        return headings

    # Sample two windows: opening (where TOC + first chapter usually appear)
    # and a midpoint (to confirm style is consistent).
    sample_size = 6000
    samples = [text[:sample_size]]
    if len(text) > sample_size * 3:
        mid = len(text) // 2
        samples.append(text[mid : mid + sample_size])
    suggested: list[re.Pattern[str]] = []
    for s in samples:
        suggested.extend(_llm_pattern_suggestions(s))
        if len(suggested) >= 6:
            break

    if not suggested:
        return headings

    headings_v2 = _find_with_patterns(text, _DEFAULT_HEADING_PATTERNS + suggested)
    return headings_v2 if len(headings_v2) > len(headings) else headings


def split_into_chapters(
    text: str,
    headings: list[Heading],
    *,
    min_prelude_chars: int = 200,
) -> list[Chapter]:
    if not headings:
        return [Chapter(index=1, title="本文", text=text.strip())]

    chapters: list[Chapter] = []

    # If there's substantial text before the first heading, keep it as ch.0.
    if headings[0].offset >= min_prelude_chars:
        prelude = text[: headings[0].offset].strip()
        if prelude:
            chapters.append(Chapter(index=0, title="冒頭", text=prelude))

    for i, h in enumerate(headings):
        end = headings[i + 1].offset if i + 1 < len(headings) else len(text)
        body = text[h.offset : end].strip()
        if not body:
            continue
        # If the body is just the heading line, skip
        if len(body) <= len(h.title) + 2:
            continue
        chapters.append(Chapter(index=len(chapters) + 1, title=h.title, text=body))

    # Re-number sequentially, keeping 0 for prelude if present
    if chapters and chapters[0].title == "冒頭" and chapters[0].index == 0:
        for i, ch in enumerate(chapters[1:], start=1):
            ch.index = i
    else:
        for i, ch in enumerate(chapters, start=1):
            ch.index = i
    return chapters
