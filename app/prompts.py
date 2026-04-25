"""System prompt and prompt assembly for the Rinri chatbot."""
from __future__ import annotations

from typing import List

from qdrant_client.http import models as qm


SYSTEM_PROMPT = """\
あなたは一般社団法人倫理研究所の刊行書籍に基づき、倫理研究所が教え伝えている内容について
日本語で丁寧に回答するアシスタントです。回答にあたっては以下の原則を厳守してください。

【役割】
- 倫理研究所の書籍・教えに沿った内容のみを扱うこと。
- 質問者(多くは職員・会員)が理解を深め、日々の実践に活かせるよう、平易で落ち着いた文体で答えること。

【回答方法】
1. 提示された【参考資料】の内容に根拠を置いて回答すること。資料外の独自解釈や創作は避ける。
2. 参考資料に該当する記述がない、または不十分な場合は、憶測せず「書籍には該当する記述が見当たりません」
   と率直に述べること。
3. 回答の末尾に、引用した参考資料の出典(ファイル名/章見出しなど)を箇条書きで示すこと。
4. 複数の記述がある場合は、それらを整理して要点を示し、必要に応じて原文の語句を引用すること。

【禁止事項】
- 医療・法律・税務・投資・宗教教義の断定的助言を行うこと。
- 個人や団体を誹謗中傷すること。
- 資料に無い内容を「倫理研究所の教え」として語ること。

【文体】
- です・ます調。敬体。
- 断定を避け、資料に書かれている内容として語る(例:「〜と述べられています」「〜とあります」)。
"""


def _format_source_label(payload: dict) -> str:
    title = (payload.get("title") or "").strip()
    chapter = (payload.get("chapter_title") or "").strip()
    if title and chapter:
        return f"{title} / {chapter}"
    if title:
        return title
    return payload.get("source", "(不明)")


def build_context(hits: List[qm.ScoredPoint]) -> str:
    blocks: list[str] = []
    for i, h in enumerate(hits, start=1):
        payload = h.payload or {}
        label = _format_source_label(payload)
        idx = payload.get("chunk_index", 0)
        text = payload.get("text", "")
        blocks.append(f"[資料{i}] 出典: {label} (chunk:{idx})\n{text}")
    return "\n\n".join(blocks)


def build_user_message(question: str, context: str) -> str:
    return f"""\
【参考資料】
{context}

【質問】
{question}

上記の【参考資料】に基づき、原則に従って日本語で回答してください。
最後に「出典」として、用いた資料番号と出典名を箇条書きで示してください。
"""
