from __future__ import annotations

from office.templates import Template


SYSTEM_PROMPT = """\
あなたは日本語の事務資料(OCR 結果)から情報を正確に抽出するアシスタントです。
与えられたスキーマに忠実な JSON オブジェクトだけを返してください。

【原則】
- 本文に書かれている事実のみを抽出し、推測や補完はしない。
- 該当する情報が見当たらない項目は null を返す。
- 数値項目はカンマ・円記号・空白を除いた純粋な整数または数値のみ。
- 日付項目は YYYY-MM-DD 形式に正規化する。和暦(令和6年4月1日 等)も西暦に直す。
- string[] 型の項目は常に配列で返す(要素が 1 つでも配列)。見つからなければ空配列 []。
- 出力は JSON オブジェクトのみ。前後に説明文・マークダウンを付けない。
- OCR によるスペース・改行・誤認識(例: 「0」と「O」、「1」と「l」)が混在しうることを理解し、
  明らかな誤認識は文脈から補正してよい。ただし意味を変える書き換えはしない。
"""


def _format_fields(template: Template) -> str:
    lines: list[str] = []
    for f in template.fields:
        parts = [f"- {f.key} ({f.label}, type={f.type}"]
        if f.description:
            parts.append(f", 説明: {f.description}")
        if f.required:
            parts.append(", 必須")
        parts.append(")")
        lines.append("".join(parts))
    return "\n".join(lines)


def build_user_prompt(template: Template, ocr_text: str) -> str:
    fields_desc = _format_fields(template)
    return f"""\
【資料種別】 {template.name}
{template.description}

【抽出スキーマ】
{fields_desc}

【OCR テキスト】
{ocr_text}

上記スキーマのキーをすべて含む JSON オブジェクトを返してください。
該当情報がない項目は null(配列型は [])にします。
"""


def build_freeform_prompt(fields: list[dict], ocr_text: str) -> str:
    fields_desc = "\n".join(f"- {f['key']}" for f in fields)
    return f"""\
【OCR テキスト】
{ocr_text}

以下の項目を抽出し、JSON オブジェクトで返してください。見つからない項目は null。

【抽出項目】
{fields_desc}
"""
