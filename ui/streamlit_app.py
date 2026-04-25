from __future__ import annotations

import json
import os

import httpx
import streamlit as st


API_URL = os.environ.get("API_URL", "http://api:8000")

st.set_page_config(page_title="倫理研究所 書籍チャット", page_icon="📖", layout="wide")

st.title("倫理研究所 書籍チャット")
st.caption("刊行書籍の内容に基づき、教えに関する質問にお答えします。")

if "messages" not in st.session_state:
    st.session_state.messages = []  # list[{role, content}]

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

prompt = st.chat_input("ご質問をどうぞ(例:朝起きの大切さについて教えてください)")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Strip out current user turn; history is prior turns only
    history = st.session_state.messages[:-1]

    with st.chat_message("assistant"):
        answer_area = st.empty()
        sources_area = st.empty()
        sources: list[dict] = []
        buffer = ""

        with httpx.stream(
            "POST",
            f"{API_URL}/chat",
            json={"question": prompt, "history": history},
            timeout=None,
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line:
                    continue
                try:
                    evt = json.loads(line)
                except json.JSONDecodeError:
                    continue
                t = evt.get("type")
                if t == "sources":
                    sources = evt.get("items", [])
                elif t == "delta":
                    buffer += evt.get("text", "")
                    answer_area.markdown(buffer)
                elif t == "done":
                    break

        if sources:
            with sources_area.expander("参照した書籍箇所を表示", expanded=False):
                for i, s in enumerate(sources, start=1):
                    title = (s.get("title") or "").strip()
                    chapter = (s.get("chapter_title") or "").strip()
                    author = (s.get("author") or "").strip()
                    if title and chapter:
                        label = f"**{title}**  〈{chapter}〉"
                    elif title:
                        label = f"**{title}**"
                    else:
                        label = f"`{s['source']}`"
                    if author:
                        label += f"   著: {author}"
                    st.markdown(
                        f"**[資料{i}]** {label}\n\n"
                        f"<small>chunk {s['chunk_index']} / score {s['score']:.3f} / file: `{s['source']}`</small>",
                        unsafe_allow_html=True,
                    )
                    st.write(s["text"])
                    st.markdown("---")

    st.session_state.messages.append({"role": "assistant", "content": buffer})
