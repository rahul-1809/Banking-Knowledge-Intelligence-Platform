import os
import sys
import time
import uuid
from pathlib import Path

# Load environment variables explicitly from the root directory
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
env_path = _ROOT / ".env"
load_dotenv(dotenv_path=env_path)

import logfire
import requests
import streamlit as st

# Initialize Logfire
try:
    token = os.getenv("LOGFIRE_TOKEN")
    if token:
        logfire.configure(token=token, service_name="bkip-ui", send_to_logfire=True)
        LOGFIRE_STATUS = "Connected & Tracing"
    else:
        logfire.configure(send_to_logfire=False, service_name="bkip-ui")
        LOGFIRE_STATUS = "Standby (No Token)"
except Exception as e:
    print(f"Logfire Init Error in UI: {e}")
    LOGFIRE_STATUS = f"Standby (Error: {e})"

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Enterprise Agentic RAG",
    page_icon="🤖",
    layout="wide",
)

# --- AVATARS ---
AI_AVATAR = "🤖"
USER_AVATAR = "👤"

# --- SESSION MANAGEMENT ---
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
    logfire.info(f"✨ New User Session Created: {st.session_state.session_id}")

if "messages" not in st.session_state:
    st.session_state.messages = []

# --- SIDEBAR ---
with st.sidebar:
    st.title("🧠 Agent OS")
    st.markdown("---")
    st.success(f"Logfire: {LOGFIRE_STATUS}")
    st.info(f"Memory ID: {st.session_state.session_id[:8]}")

    if st.button("🗑️ Clear History & Memory", use_container_width=True, type="primary"):
        logfire.warn(f"🗑️ Memory Wipe Triggered for session: {st.session_state.session_id}")
        st.session_state.messages = []
        st.session_state.session_id = str(uuid.uuid4())
        st.rerun()

    st.markdown("---")
    st.markdown("### 📥 Ingest Document")
    uploaded_file = st.file_uploader(
        "Upload file to ingest & index",
        type=["pdf", "txt", "docx", "json", "md"],
        help="Upload PDF, TXT, DOCX, JSON, or MD documents into the vector database for RAG retrieval.",
    )
    custom_cat = st.text_input(
        "Category (Optional)",
        placeholder="e.g. RBI, SOP, CUSTOM",
        help="Optional category metadata for document indexing.",
    )

    if uploaded_file is not None:
        if st.button("⚡ Ingest & Index File", use_container_width=True):
            with st.spinner(f"Parsing, embedding & indexing '{uploaded_file.name}'..."):
                try:
                    base_url = os.getenv("BACKEND_URL", "http://localhost:8000")
                    url = f"{base_url}/ingest"
                    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type or "application/octet-stream")}
                    data_form = {}
                    if custom_cat.strip():
                        data_form["category"] = custom_cat.strip()

                    res = requests.post(url, files=files, data=data_form, timeout=120)
                    res.raise_for_status()
                    ingest_res = res.json()

                    st.success(
                        f"✅ **Ingested {ingest_res.get('file_name')}**!\n\n"
                        f"- Chunks: `{ingest_res.get('chunks_ingested')}`\n"
                        f"- Category: `{ingest_res.get('category')}`"
                    )
                    logfire.info(f"📥 File ingested via UI: {uploaded_file.name}")
                except Exception as exc:
                    st.error(f"❌ Ingestion Error: {exc}")
                    logfire.error(f"❌ File ingestion failed: {exc}")

# --- MAIN CHAT ---
st.title("🤖 Enterprise Agentic Assistant")

# Display history
for message in st.session_state.messages:
    avatar = AI_AVATAR if message["role"] == "assistant" else USER_AVATAR
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])

        # Display thought process if available in history
        if message.get("thought_process"):
            with st.expander("⚙️ Agent Reasoning Steps", expanded=False):
                for step in message["thought_process"]:
                    st.write(f"⚙️ {step}")

        # Display sources if available in history
        if message.get("sources"):
            with st.expander("📄 View Retrieved Context (Sources)", expanded=False):
                for i, source in enumerate(message["sources"]):
                    if isinstance(source, dict):
                        file_name = source.get("file_name", f"Document {i+1}")
                        score = source.get("score", 0.0)
                        text = source.get("text", "")
                        st.markdown(f"**Chunk {i+1}:** `{file_name}` *(Relevance Score: {score})*")
                        st.info(text)
                    else:
                        st.markdown(f"**Chunk {i+1}:**")
                        st.info(str(source))

# Chat Input
if prompt := st.chat_input("Ask about your documentation..."):
    # START TRACE: User Interaction
    with logfire.span("💬 User Chat Interaction", user_query=prompt, session_id=st.session_state.session_id):

        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar=USER_AVATAR):
            st.markdown(prompt)

        # Assistant Response
        with st.chat_message("assistant", avatar=AI_AVATAR):
            with st.status("🔍 Agent is thinking...", expanded=True) as status:
                try:
                    # DISTRIBUTED TRACE: Calling Backend
                    with logfire.span("📡 Calling RAG Backend"):
                        base_url = os.getenv("BACKEND_URL", "http://localhost:8000")
                        url = f"{base_url}/query"
                        payload = {"message": prompt, "q": prompt, "thread_id": st.session_state.session_id}
                        response = requests.post(url, json=payload, timeout=60)
                        response.raise_for_status()
                        data = response.json()

                    blocked = data.get("blocked", False)

                    # Show Reasoning Steps from Backend
                    steps = data.get("thought_process", [])
                    for step in steps:
                        st.write(f"⚙️ {step}")

                    if blocked:
                        status.update(label="⛔ Request Blocked by Guardrails", state="error", expanded=False)
                    else:
                        status.update(label="✅ Answer Synthesized", state="complete", expanded=False)
                except Exception as e:
                    logfire.error(f"❌ UI-Backend Connection Failed: {e}")
                    status.update(label="❌ Connection Failed", state="error")
                    st.error(f"Backend Connection Error: {e}")
                    st.stop()

            # --- SHOW SOURCES (Rendered outside st.status to avoid nested expander error) ---
            sources = data.get("sources", [])
            if sources:
                with st.expander("📄 View Retrieved Context (Sources)", expanded=False):
                    for i, source in enumerate(sources):
                        if isinstance(source, dict):
                            file_name = source.get("file_name", f"Chunk {i+1}")
                            score = source.get("score", 0.0)
                            text = source.get("text", str(source))
                            st.markdown(f"**Chunk {i+1}:** `{file_name}` *(Relevance Score: {score})*")
                            st.info(text)
                        else:
                            st.markdown(f"**Chunk {i+1}:**")
                            st.info(str(source))

            # Final Answer Streaming
            answer_placeholder = st.empty()
            full_answer = data.get("answer", "No response.")

            curr_text = ""
            for char in full_answer:
                curr_text += char
                answer_placeholder.markdown(curr_text + "▌")
                time.sleep(0.005)

            answer_placeholder.markdown(full_answer)
            st.session_state.messages.append({
                "role": "assistant",
                "content": full_answer,
                "sources": data.get("sources", []),
                "thought_process": data.get("thought_process", [])
            })
            logfire.info("✅ Chat cycle completed successfully.")
