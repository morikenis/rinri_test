from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from office.extractor import ExtractorError, extract_json
from office.ocr import ocr_file
from office.prompts import SYSTEM_PROMPT, build_freeform_prompt, build_user_prompt
from office.templates import TEMPLATES, find_template


st.set_page_config(page_title="事務資料 情報抽出", page_icon="📄", layout="wide")
st.title("事務資料 情報抽出")
st.caption("紙をスキャンした PDF / 画像から、項目を構造化して取り出します。")

# --- Step 1: upload ----------------------------------------------------------
uploaded = st.file_uploader(
    "資料をアップロード(PDF / PNG / JPG)",
    type=["pdf", "png", "jpg", "jpeg"],
    accept_multiple_files=False,
)

if not uploaded:
    st.info("ファイルをアップロードすると、OCR と抽出フォームが表示されます。")
    st.stop()

# --- Step 2: OCR -------------------------------------------------------------
if (
    "ocr_text" not in st.session_state
    or st.session_state.get("ocr_key") != uploaded.name
):
    with st.spinner("OCR 中..."):
        data = uploaded.getvalue()
        text = ocr_file(uploaded.name, data)
    st.session_state.ocr_text = text
    st.session_state.ocr_key = uploaded.name

ocr_text: str = st.session_state.ocr_text

with st.expander("OCR 結果を表示 / 編集", expanded=False):
    edited = st.text_area(
        "OCR テキスト(誤認識があればここで修正可)",
        value=ocr_text,
        height=320,
        key="ocr_editor",
    )
    st.session_state.ocr_text = edited
    ocr_text = edited

# --- Step 3: template choice -------------------------------------------------
st.subheader("抽出テンプレートを選ぶ")
col1, col2 = st.columns([1, 2])

template_keys = [t.key for t in TEMPLATES] + ["freeform"]
template_labels = {t.key: t.name for t in TEMPLATES}
template_labels["freeform"] = "自由入力"

with col1:
    choice = st.radio(
        "種別",
        options=template_keys,
        format_func=lambda k: template_labels[k],
    )

fields_list: list[dict] = []

with col2:
    if choice == "freeform":
        st.markdown("抽出したい項目を 1 行 1 項目で入力してください。")
        raw = st.text_area(
            "項目",
            value="氏名\n会社名\n金額\n日付",
            height=180,
            key="freeform_fields",
        )
        fields_list = [
            {"key": line.strip()} for line in raw.splitlines() if line.strip()
        ]
    else:
        tmpl = find_template(choice)
        assert tmpl is not None
        if tmpl.description:
            st.markdown(f"**{tmpl.name}** — {tmpl.description}")
        else:
            st.markdown(f"**{tmpl.name}**")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "項目": f.label,
                        "キー": f.key,
                        "型": f.type,
                        "必須": "○" if f.required else "",
                    }
                    for f in tmpl.fields
                ]
            ),
            hide_index=True,
            use_container_width=True,
        )

# --- Step 4: extract ---------------------------------------------------------
if st.button("抽出する", type="primary"):
    if choice == "freeform":
        if not fields_list:
            st.warning("抽出項目を入力してください。")
            st.stop()
        user_prompt = build_freeform_prompt(fields_list, ocr_text)
    else:
        tmpl = find_template(choice)
        assert tmpl is not None
        user_prompt = build_user_prompt(tmpl, ocr_text)

    try:
        with st.spinner("Gemma 4 が抽出中... (初回は VRAM ロードで数十秒かかります)"):
            result = extract_json(SYSTEM_PROMPT, user_prompt)
    except ExtractorError as e:
        st.error(f"抽出に失敗しました: {e}")
        st.stop()
    except Exception as e:  # noqa: BLE001
        st.error(f"抽出中にエラーが発生しました: {e}")
        st.stop()

    st.success("抽出完了")

    # Build a flat review table
    rows: list[dict] = []
    for k, v in result.items():
        if isinstance(v, list):
            display = "\n".join(str(x) for x in v)
        elif v is None:
            display = ""
        else:
            display = str(v)
        rows.append({"項目": k, "値": display})
    df = pd.DataFrame(rows)

    st.dataframe(df, hide_index=True, use_container_width=True)

    with st.expander("生の JSON を表示", expanded=False):
        st.json(result)

    csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "CSV ダウンロード",
        data=csv_bytes,
        file_name=f"extracted_{uploaded.name}.csv",
        mime="text/csv",
    )
    st.download_button(
        "JSON ダウンロード",
        data=json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8"),
        file_name=f"extracted_{uploaded.name}.json",
        mime="application/json",
    )
