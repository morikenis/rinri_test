from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


FieldType = Literal["string", "number", "date", "string[]"]


@dataclass
class TemplateField:
    key: str
    label: str
    type: FieldType = "string"
    description: str = ""
    required: bool = False


@dataclass
class Template:
    key: str
    name: str
    description: str
    fields: list[TemplateField] = field(default_factory=list)


TEMPLATES: list[Template] = [
    Template(
        key="invoice",
        name="請求書",
        description="取引先から受領した請求書の主要情報を抽出します。",
        fields=[
            TemplateField("issuer", "請求元", "string", "請求書を発行した会社名", required=True),
            TemplateField("recipient", "請求先", "string", "請求を受ける会社・個人名"),
            TemplateField("issue_date", "請求日", "date", "YYYY-MM-DD"),
            TemplateField("due_date", "支払期限", "date", "YYYY-MM-DD"),
            TemplateField("subject", "件名", "string"),
            TemplateField("subtotal", "小計", "number", "税抜き金額(円、整数)"),
            TemplateField("tax", "消費税", "number", "円"),
            TemplateField("total", "合計金額", "number", "税込合計(円)", required=True),
            TemplateField("bank_account", "振込先", "string", "銀行名・支店・口座種別・番号"),
            TemplateField("invoice_number", "請求書番号", "string"),
        ],
    ),
    Template(
        key="receipt",
        name="領収書",
        description="",
        fields=[
            TemplateField("issuer", "発行者", "string", required=True),
            TemplateField("recipient", "宛名", "string"),
            TemplateField("amount", "金額", "number", "円", required=True),
            TemplateField("issue_date", "日付", "date"),
            TemplateField("note", "但し書き", "string"),
        ],
    ),
    Template(
        key="quotation",
        name="見積書",
        description="",
        fields=[
            TemplateField("issuer", "発行者", "string", required=True),
            TemplateField("recipient", "宛先", "string"),
            TemplateField("subject", "件名", "string"),
            TemplateField("issue_date", "発行日", "date"),
            TemplateField("valid_until", "有効期限", "date"),
            TemplateField("subtotal", "小計", "number"),
            TemplateField("tax", "消費税", "number"),
            TemplateField("total", "合計金額", "number"),
        ],
    ),
    Template(
        key="proposal",
        name="稟議書",
        description="",
        fields=[
            TemplateField("proposer", "起案者", "string", required=True),
            TemplateField("proposal_date", "起案日", "date"),
            TemplateField("subject", "件名", "string", required=True),
            TemplateField("summary", "概要", "string"),
            TemplateField("amount", "金額", "number"),
            TemplateField("approvers", "承認者", "string[]", "承認欄に記名されている氏名のリスト"),
        ],
    ),
    Template(
        key="minutes",
        name="議事録",
        description="",
        fields=[
            TemplateField("date_time", "日時", "string"),
            TemplateField("location", "場所", "string"),
            TemplateField("attendees", "出席者", "string[]"),
            TemplateField("agenda", "議題", "string[]"),
            TemplateField("decisions", "決定事項", "string[]"),
            TemplateField("todos", "ToDo", "string[]", "担当者と期限を含めて可読な一文で"),
        ],
    ),
    Template(
        key="business_card",
        name="名刺",
        description="",
        fields=[
            TemplateField("name", "氏名", "string", required=True),
            TemplateField("name_reading", "氏名(ふりがな)", "string"),
            TemplateField("company", "会社名", "string"),
            TemplateField("department", "所属部署", "string"),
            TemplateField("title", "役職", "string"),
            TemplateField("email", "メールアドレス", "string"),
            TemplateField("phone", "電話番号", "string"),
            TemplateField("mobile", "携帯番号", "string"),
            TemplateField("postal_code", "郵便番号", "string"),
            TemplateField("address", "住所", "string"),
            TemplateField("website", "Webサイト", "string"),
        ],
    ),
]


def find_template(key: str) -> Template | None:
    for t in TEMPLATES:
        if t.key == key:
            return t
    return None
