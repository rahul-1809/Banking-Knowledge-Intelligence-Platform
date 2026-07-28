"""Planner node — classifies user intent and routes the graph accordingly.

Phase 5: Logfire span wraps the full node; LangSmith callback attached to LLM call.
"""

from __future__ import annotations

import time

import logfire
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.state import AgentState
from app.core.logging import get_logger
from app.core.tracing import get_langsmith_callbacks
from app.gateway.llm_client import get_planner_llm

logger = get_logger(__name__)

PLANNER_SYSTEM_PROMPT = """You are the Planner for a Banking Knowledge Intelligence Platform.

Your only job is to classify the user's intent into exactly ONE of these two labels:

CONVERSATIONAL
  - Greetings, pleasantries, thank-yous, capability questions, meta questions
    about the assistant (e.g., "Hello", "What can you help me with?", "Thanks!")

BANKING_POLICY_QUERY
  - Any question about banking regulations, RBI circulars, KYC/AML rules, credit
    policy, internal SOPs, compliance requirements, interest rates, account rules,
    loan eligibility, banking procedures, or any factual banking domain query.

Respond with ONLY the label — no explanation, no punctuation, no extra words.
If in doubt, default to BANKING_POLICY_QUERY."""


def planner_node(state: AgentState) -> dict:
    """Classify intent and set the ``intent`` field in state.

    Reads the last human message from ``state["messages"]`` (or falls back to
    ``state["query"]``) and calls the primary LLM to output a single intent
    label.  Appends a reasoning entry to ``thought_process``.

    Phase 5: Full Logfire tracing + LangSmith callback + Portkey metadata/caching.
    """
    query = state.get("query", "")
    thread_id = state.get("thread_id", "")
    thought_process = list(state.get("thought_process", []))

    with logfire.span(
        "agent.planner",
        query_preview=query[:80],
        query_len=len(query),
    ):
        logger.info("Planner evaluating query: %r", query[:80])
        t0 = time.perf_counter()

        messages = [
            SystemMessage(content=PLANNER_SYSTEM_PROMPT),
            HumanMessage(content=query),
        ]

        metadata = {"node": "planner", "thread_id": thread_id}
        llm = get_planner_llm(metadata=metadata)
        callbacks = get_langsmith_callbacks()
        response = llm.invoke(messages, config={"callbacks": callbacks})
        raw_label = response.content.strip().upper()
        latency_ms = round((time.perf_counter() - t0) * 1000, 1)

        # Normalise to one of the two valid labels.
        if "CONVERSATIONAL" in raw_label:
            intent = "CONVERSATIONAL"
        else:
            intent = "BANKING_POLICY_QUERY"

        thought_process.append(f"[Planner] Intent classified as: {intent}")
        logger.info("Planner intent=%s latency=%.1fms", intent, latency_ms)

        logfire.info(
            "agent.planner.complete",
            intent=intent,
            latency_ms=latency_ms,
            query_len=len(query),
        )

    return {
        "intent": intent,
        "thought_process": thought_process,
    }

