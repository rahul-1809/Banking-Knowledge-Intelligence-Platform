"""BKIP Enterprise Chat UI — Phase 5/6.

Design: Modern dark-mode chat with Logfire session tracing, streaming answers,
nested source expanders, and real-time agent reasoning steps.

Run with:
    streamlit run ui/app.py
"""

from __future__ import annotations

import os
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

# Bootstrap project root so imports work from any working directory.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Load .env from project root before any other imports.
from dotenv import load_dotenv  # type: ignore[import-untyped]
load_dotenv(dotenv_path=_ROOT / ".env")

import logfire
import requests
import streamlit as st

# ── Logfire bootstrap ─────────────────────────────────────────────────────────
_logfire_token = os.getenv("LOGFIRE_TOKEN", "")
try:
    if _logfire_token:
        logfire.configure(token=_logfire_token, service_name="bkip-ui", send_to_logfire=True)
    else:
        logfire.configure(send_to_logfire=False, service_name="bkip-ui")
    LOGFIRE_STATUS = "Connected & Tracing"
except Exception as _e:
    LOGFIRE_STATUS = f"Standby (Error: {_e})"

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="BKIP — Enterprise Banking Assistant",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Constants ─────────────────────────────────────────────────────────────────
API_BASE = os.getenv("BACKEND_URL", "http://localhost:8000")
TIMEOUT = 120.0
AI_AVATAR = "🤖"
USER_AVATAR = "👤"
CATEGORIES = ["(all)", "RBI", "SOP", "CREDIT", "COMPLIANCE", "TREASURY", "AUDIT"]

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.stApp {
    background: linear-gradient(135deg, #0a0a14 0%, #12121f 50%, #0d1526 100%);
    color: #e2e8f0;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: rgba(15, 15, 30, 0.85);
    border-right: 1px solid rgba(99,102,241,0.2);
    backdrop-filter: blur(12px);
}

/* Status badge */
.status-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 12px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.3px;
}
.badge-green { background: rgba(16,185,129,0.15); color: #34d399; border: 1px solid rgba(52,211,153,0.3); }
.badge-blue  { background: rgba(99,102,241,0.15); color: #818cf8; border: 1px solid rgba(129,140,248,0.3); }
.badge-red   { background: rgba(239,68,68,0.15);  color: #f87171; border: 1px solid rgba(248,113,113,0.3); }

/* Page header */
.page-header {
    background: linear-gradient(135deg, rgba(99,102,241,0.15), rgba(139,92,246,0.1));
    border: 1px solid rgba(99,102,241,0.25);
    border-radius: 16px;
    padding: 1.4rem 1.8rem;
    margin-bottom: 1.5rem;
}
.page-header h1 {
    margin: 0; font-size: 1.6rem; font-weight: 700;
    background: linear-gradient(135deg, #818cf8, #c4b5fd);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.page-header p { margin: 0.3rem 0 0; font-size: 0.82rem; color: #94a3b8; }

/* Thought step */
.thought-step {
    background: rgba(99,102,241,0.08);
    border-left: 2px solid #6366f1;
    border-radius: 0 8px 8px 0;
    padding: 0.45rem 0.8rem;
    margin-bottom: 0.35rem;
    font-size: 0.78rem;
    color: #a5b4fc;
    font-family: 'Courier New', monospace;
}

/* Source card */
.source-card {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-left: 3px solid #6366f1;
    border-radius: 8px;
    padding: 0.75rem 1rem;
    margin-bottom: 0.5rem;
}
.source-meta { font-size: 0.8rem; font-weight: 600; color: #818cf8; margin-bottom: 0.3rem; }
.source-cat  { font-size: 0.72rem; color: #64748b; margin-bottom: 0.5rem; }
.source-text { font-size: 0.78rem; color: #94a3b8; line-height: 1.55; }
.score-badge {
    display: inline-block;
    background: rgba(99,102,241,0.2); color: #a5b4fc;
    border-radius: 4px; padding: 1px 7px;
    font-size: 0.7rem; font-weight: 600; margin-left: 8px;
}

/* Blocked warning */
.blocked-banner {
    background: rgba(239,68,68,0.1); border: 1px solid rgba(239,68,68,0.3);
    border-radius: 10px; padding: 0.85rem 1.1rem;
    color: #fca5a5; font-size: 0.88rem;
}

/* Chat input */
.stChatInput > div { border-radius: 12px !important; }
div[data-testid="stChatInput"] textarea {
    background: rgba(255,255,255,0.05) !important;
    border: 1px solid rgba(99,102,241,0.3) !important;
    border-radius: 12px !important;
    color: #e2e8f0 !important;
}

hr { border-color: rgba(255,255,255,0.06); }
</style>
""", unsafe_allow_html=True)


# ── Session state ─────────────────────────────────────────────────────────────

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
    logfire.info("bkip.ui.new_session", session_id=st.session_state.session_id)

if "messages" not in st.session_state:
    # Each entry: {"role": str, "content": str, "sources": list, "thought_process": list, "blocked": bool}
    st.session_state.messages = []

if "filter_category" not in st.session_state:
    st.session_state.filter_category = "(all)"

if "filter_file" not in st.session_state:
    st.session_state.filter_file = ""


# ── API helpers ───────────────────────────────────────────────────────────────

def call_health() -> dict:
    try:
        r = requests.get(f"{API_BASE}/health", timeout=5.0)
        return r.json()
    except Exception:
        return {"status": "unreachable", "qdrant": "unavailable", "logfire": "inactive", "langsmith": "inactive"}


def call_query(message: str, thread_id: str, category: Optional[str], file_name: Optional[str]) -> dict:
    payload: dict = {"message": message, "thread_id": thread_id}
    if category or file_name:
        payload["filters"] = {}
        if category:
            payload["filters"]["category"] = category
        if file_name:
            payload["filters"]["file_name"] = file_name

    r = requests.post(f"{API_BASE}/query", json=payload, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### 🏦 BKIP")
    st.markdown("**Banking Knowledge Intelligence Platform**")
    st.markdown("---")

    # Health status
    health = call_health()
    api_ok = health.get("status") == "ok"
    qd_ok  = health.get("qdrant") == "connected"
    lf_ok  = health.get("logfire") == "active"
    ls_ok  = health.get("langsmith") == "active"

    st.markdown(
        f'<span class="status-badge {"badge-green" if api_ok else "badge-red"}">⬤ API {health.get("status","—")}</span>&nbsp;'
        f'<span class="status-badge {"badge-green" if qd_ok else "badge-red"}">⬤ Qdrant {health.get("qdrant","—")}</span>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<span class="status-badge {"badge-green" if lf_ok else "badge-blue"}">⬤ Logfire {"active" if lf_ok else "inactive"}</span>&nbsp;'
        f'<span class="status-badge {"badge-green" if ls_ok else "badge-blue"}">⬤ LangSmith {"active" if ls_ok else "inactive"}</span>',
        unsafe_allow_html=True,
    )
    st.markdown("")

    # Logfire UI status
    logfire_chip_cls = "badge-green" if "Connected" in LOGFIRE_STATUS else "badge-blue"
    st.markdown(
        f'<span class="status-badge {logfire_chip_cls}">🔭 UI: {LOGFIRE_STATUS}</span>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<span class="status-badge badge-blue">🔑 Session: {st.session_state.session_id[:8]}…</span>',
        unsafe_allow_html=True,
    )
    st.markdown("---")

    # Retrieval filters
    st.markdown("#### 🔍 Retrieval Filters")
    filter_category = st.selectbox(
        "Document Category",
        CATEGORIES,
        index=CATEGORIES.index(st.session_state.filter_category),
        help="Restrict retrieval to one document category.",
    )
    filter_file = st.text_input(
        "File Name (exact)",
        value=st.session_state.filter_file,
        placeholder="e.g. rbi_master_direction_kyc.pdf",
        help="Pin retrieval to a specific source document.",
    )
    st.session_state.filter_category = filter_category
    st.session_state.filter_file = filter_file
    st.markdown("---")

    # Clear history
    if st.button("🗑️ Clear History & New Session", use_container_width=True, type="primary"):
        logfire.warn(
            "bkip.ui.session_cleared",
            old_session=st.session_state.session_id,
        )
        st.session_state.messages = []
        st.session_state.session_id = str(uuid.uuid4())
        logfire.info("bkip.ui.new_session", session_id=st.session_state.session_id)
        st.rerun()

    st.markdown(
        '<p style="font-size:0.7rem;color:#334155;margin-top:1rem;">'
        'Phase 6 · LangGraph + Groq<br>Qdrant Cloud · FlashRank · RAGAS</p>',
        unsafe_allow_html=True,
    )


# ── Main layout ───────────────────────────────────────────────────────────────

col_chat, col_panel = st.columns([6, 4], gap="large")

with col_chat:
    st.markdown("""
    <div class="page-header">
        <h1>🏦 Enterprise Banking Assistant</h1>
        <p>Ask about RBI circulars, KYC/AML policies, SOPs, credit rules, and internal banking procedures.</p>
    </div>
    """, unsafe_allow_html=True)

    # Render message history
    for entry in st.session_state.messages:
        if entry["role"] == "user":
            with st.chat_message("user", avatar=USER_AVATAR):
                st.markdown(entry["content"])
        else:
            with st.chat_message("assistant", avatar=AI_AVATAR):
                if entry.get("blocked"):
                    st.markdown(
                        f'<div class="blocked-banner">⛔ <strong>Request Blocked</strong><br>{entry["content"]}</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(entry["content"])

    # Chat input
    if prompt := st.chat_input("Ask about banking regulations, KYC, credit policy…"):
        with logfire.span(
            "bkip.ui.user_interaction",
            session_id=st.session_state.session_id,
            query_preview=prompt[:80],
        ):
            # Show user message immediately
            st.session_state.messages.append(
                {"role": "user", "content": prompt, "sources": [], "thought_process": [], "blocked": False}
            )
            with st.chat_message("user", avatar=USER_AVATAR):
                st.markdown(prompt)

            category_val = filter_category if filter_category != "(all)" else None
            file_val = filter_file.strip() or None

            # Assistant turn
            with st.chat_message("assistant", avatar=AI_AVATAR):
                with st.status("🔍 Agent is thinking…", expanded=True) as status_box:
                    try:
                        with logfire.span(
                            "bkip.ui.api_call",
                            session_id=st.session_state.session_id,
                            category=category_val or "none",
                        ):
                            result = call_query(
                                message=prompt,
                                thread_id=st.session_state.session_id,
                                category=category_val,
                                file_name=file_val,
                            )

                        # Show agent reasoning steps live
                        steps = result.get("thought_process", [])
                        for step in steps:
                            st.write(f"⚙️ {step}")

                        blocked = result.get("blocked", False)

                        if blocked:
                            status_box.update(label="⛔ Request Blocked by Guardrails", state="error", expanded=False)
                        else:
                            status_box.update(label="✅ Answer Synthesised", state="complete", expanded=False)

                    except requests.exceptions.ConnectionError:
                        logfire.error("bkip.ui.connection_error", backend=API_BASE)
                        status_box.update(label="❌ Cannot reach API", state="error")
                        st.error(f"❌ Cannot reach the API at `{API_BASE}`. Is `uvicorn app.main:app` running?")
                        st.stop()
                    except Exception as exc:
                        logfire.error("bkip.ui.error", error=str(exc))
                        status_box.update(label="❌ Error", state="error")
                        st.error(f"Unexpected error: {exc}")
                        st.stop()

                if blocked:
                    answer = result.get("answer", "This request cannot be processed.")
                    st.markdown(
                        f'<div class="blocked-banner">⛔ <strong>Blocked</strong> — {result.get("reason","policy_violation")}<br>{answer}</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    # Stream the answer character-by-character
                    answer = result.get("answer", "No response received.")
                    answer_placeholder = st.empty()
                    curr_text = ""
                    for char in answer:
                        curr_text += char
                        answer_placeholder.markdown(curr_text + "▌")
                        time.sleep(0.005)
                    answer_placeholder.markdown(answer)

            # Save to history
            st.session_state.messages.append({
                "role": "assistant",
                "content": answer,
                "sources": result.get("sources", []),
                "thought_process": result.get("thought_process", []),
                "blocked": blocked,
            })
            logfire.info(
                "bkip.ui.response",
                session_id=st.session_state.session_id,
                sources_count=len(result.get("sources", [])),
                blocked=blocked,
                answer_len=len(answer),
            )
            st.rerun()


# ── Right panel: Sources & Reasoning ─────────────────────────────────────────

with col_panel:
    st.markdown("### 📄 Sources & Reasoning")

    # Find last assistant entry with data
    last_assistant = next(
        (e for e in reversed(st.session_state.messages) if e["role"] == "assistant"),
        None,
    )

    if last_assistant:
        sources = last_assistant.get("sources", [])
        thought_process = last_assistant.get("thought_process", [])
        blocked = last_assistant.get("blocked", False)

        if blocked:
            st.markdown(
                '<div class="blocked-banner">⛔ This request was blocked by the guardrails.</div>',
                unsafe_allow_html=True,
            )

        # Agent reasoning
        if thought_process:
            with st.expander("🧠 Agent Reasoning", expanded=True):
                for step in thought_process:
                    st.markdown(
                        f'<div class="thought-step">{step}</div>',
                        unsafe_allow_html=True,
                    )

        # Retrieved sources (nested expanders)
        if sources:
            st.markdown(f"**{len(sources)} source chunk(s) retrieved:**")
            for i, src in enumerate(sources):
                # src is a dict: {file_name, chunk_index, score, text, category}
                score_pct = f"{src['score'] * 100:.1f}%"
                text_preview = src["text"][:200] + ("…" if len(src["text"]) > 200 else "")
                label = f"📎 [{i+1}] {src['file_name']} — score {score_pct}"
                with st.expander(label):
                    st.markdown(
                        f'<div class="source-card">'
                        f'<div class="source-meta">📎 {src["file_name"]}'
                        f'<span class="score-badge">score {score_pct}</span></div>'
                        f'<div class="source-cat">Chunk #{src["chunk_index"]} · {src["category"]}</div>'
                        f'<div class="source-text">{text_preview}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
        elif not blocked:
            st.markdown(
                '<p style="color:#475569;font-size:0.83rem;">No documents retrieved (conversational response).</p>',
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            '<p style="color:#334155;font-size:0.85rem;">Ask a question to see retrieved sources and agent reasoning here.</p>',
            unsafe_allow_html=True,
        )
