"""Responder node — synthesises the final answer from retrieved context.

Phase 5: Logfire span wraps the full node; LangSmith callback attached to LLM call.
"""

from __future__ import annotations

import time

import logfire
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agents.state import AgentState
from app.core.logging import get_logger
from app.core.tracing import get_langsmith_callbacks
from app.gateway.llm_client import get_primary_llm

logger = get_logger(__name__)

BANKING_RESPONDER_SYSTEM = """You are a compliance-aware AI assistant for a Banking Knowledge Intelligence Platform.

You answer questions about banking regulations, RBI circulars, KYC/AML policies, SOPs, credit policy, and other banking domain topics.

RULES:
1. Ground every factual claim in the provided context documents.
2. Always cite your source(s) using the format: [Source: <file_name>, Chunk <chunk_index>].
3. If the context does not contain enough information, say so clearly — do NOT fabricate facts.
4. Keep your answer concise, structured, and professional.
5. Never reveal personal financial data, Aadhaar numbers, PAN, or account numbers from the context.

CONTEXT DOCUMENTS:
{context}
"""

CONVERSATIONAL_RESPONDER_SYSTEM = """You are a helpful AI assistant for a Banking Knowledge Intelligence Platform (BKIP).

You handle greetings, meta questions, and capability inquiries.

CAPABILITIES you can describe:
- Answer questions about banking regulations, RBI circulars, KYC/AML policies, SOPs, credit rules.
- Search and cite source documents.
- Maintain conversation context within a session.

Keep responses friendly, concise, and helpful."""


def _format_context(documents: list[dict]) -> str:
    """Format retrieved chunks into a numbered context block."""
    if not documents:
        return "(No documents retrieved)"
    parts = []
    for i, doc in enumerate(documents, start=1):
        parts.append(
            f"[{i}] File: {doc.get('file_name', 'unknown')} | "
            f"Chunk: {doc.get('chunk_index', '?')} | "
            f"Score: {doc.get('score', 0.0):.4f}\n"
            f"{doc.get('text', '')}"
        )
    return "\n\n---\n\n".join(parts)


def responder_node(state: AgentState) -> dict:
    """Generate the final answer and return updated state.

    For BANKING_POLICY_QUERY intent the node injects retrieved documents as
    context.  For CONVERSATIONAL intent it uses a capability-describing system
    prompt and skips document grounding.

    The AI response is appended to ``messages`` via an ``AIMessage`` so
    LangGraph's ``add_messages`` reducer updates the conversation history, and
    ``MemorySaver`` persists it across turns.

    Phase 5: Full Logfire tracing + LangSmith callback wired to LLM call.
    """
    query = state.get("query", "")
    intent = state.get("intent", "BANKING_POLICY_QUERY")
    documents = state.get("documents", [])
    thought_process = list(state.get("thought_process", []))

    with logfire.span(
        "agent.responder",
        intent=intent,
        docs_count=len(documents),
        query_preview=query[:80],
    ) as span:
        llm = get_primary_llm()
        callbacks = get_langsmith_callbacks()
        t0 = time.perf_counter()

        if intent == "CONVERSATIONAL":
            system_prompt = CONVERSATIONAL_RESPONDER_SYSTEM
            thought_process.append("[Responder] Handling conversational turn (no retrieval).")
            llm_messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=query),
            ]
        else:
            context = _format_context(documents)
            system_prompt = BANKING_RESPONDER_SYSTEM.format(context=context)
            thought_process.append(
                f"[Responder] Synthesising answer from {len(documents)} retrieved chunks."
            )
            llm_messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=query),
            ]

        logger.info("Responder generating answer for intent=%s", intent)
        response = llm.invoke(llm_messages, config={"callbacks": callbacks})
        answer_text = response.content.strip()
        latency_ms = round((time.perf_counter() - t0) * 1000, 1)

        span.set_attribute("response.answer", answer_text)
        span.set_attribute("response.length", len(answer_text))

        thought_process.append("[Responder] Answer generated successfully.")
        logger.info(
            "Responder produced answer (%s chars) intent=%s latency=%.1fms",
            len(answer_text),
            intent,
            latency_ms,
        )

        logfire.info(
            "agent.responder.complete",
            intent=intent,
            docs_count=len(documents),
            answer=answer_text,
            answer_len=len(answer_text),
            latency_ms=latency_ms,
        )

    return {
        "messages": [AIMessage(content=answer_text)],
        "thought_process": thought_process,
    }
