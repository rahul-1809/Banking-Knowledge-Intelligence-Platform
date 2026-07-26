"""FastAPI entrypoint — Phase 5: Logfire + LangSmith observability wired in.

IMPORT ORDER MATTERS for Logfire:
    logfire.configure() must be called BEFORE any instrumented library is
    imported, so it appears at the very top of this module (before FastAPI,
    LangGraph, etc.).  The lifespan then calls logfire.instrument_fastapi()
    on the app instance once it exists.
"""

from __future__ import annotations

# ── Step 1: Logfire must be configured before any other imports ───────────────
# ── Step 0: Load .env so os.getenv() reads the right values at import time ────
# Must happen before logfire.configure() and os.getenv("LANGSMITH_*") below.
from pathlib import Path as _Path
from dotenv import load_dotenv as _load_dotenv  # type: ignore[import-untyped]
_load_dotenv(dotenv_path=_Path(__file__).resolve().parent.parent / ".env")

import os
import logfire

# Read token directly from env here (before pydantic-settings loads) so that
# logfire captures spans from the very first import of langchain / langgraph.
_logfire_token = os.getenv("LOGFIRE_TOKEN", "")
if _logfire_token:
    logfire.configure(
        token=_logfire_token,
        service_name="bkip-api",
        service_version="0.6.0",
        send_to_logfire=True,
    )
else:
    # No token → scrub-mode: spans captured locally, never shipped.
    logfire.configure(send_to_logfire=False, service_name="bkip-api")

# Auto-trace all outbound HTTP calls (Groq API, Qdrant REST) as child spans.
try:
    logfire.instrument_httpx(capture_all=True)
except Exception:  # noqa: BLE001
    pass  # httpx may not be installed in all environments

# ── Step 2: Activate LangSmith tracing via env vars ──────────────────────────
# Support both LANGCHAIN_* (older) and LANGSMITH_* (newer) naming conventions.
_ls_key = (
    os.getenv("LANGSMITH_API_KEY")
    or os.getenv("LANGCHAIN_API_KEY", "")
)
_ls_tracing = (
    os.getenv("LANGSMITH_TRACING", "false").lower() == "true"
    or os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
)
_ls_project = (
    os.getenv("LANGSMITH_PROJECT")
    or os.getenv("LANGCHAIN_PROJECT", "bkip")
)
if _ls_key and _ls_tracing:
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = _ls_key
    os.environ["LANGCHAIN_PROJECT"] = _ls_project

# ── Step 3: Now import everything else ───────────────────────────────────────
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from app.agents.graph import get_graph
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.guardrails.rails import guard
from app.services.retrieval.vector_store import check_qdrant_health

logger = get_logger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    settings = get_settings()
    ls_active = bool(_ls_key and _ls_tracing)
    logger.info(
        "BKIP starting — collection=%s portkey=%s logfire=%s langsmith=%s",
        settings.qdrant_collection_name,
        bool(settings.portkey_api_key),
        bool(settings.logfire_token),
        ls_active,
    )
    # Pre-warm the graph so the first request doesn't pay compilation cost.
    get_graph()
    yield
    logger.info("BKIP shutting down")


# ── Pydantic models ────────────────────────────────────────────────────────────


class QueryFilters(BaseModel):
    category: Optional[str] = None
    file_name: Optional[str] = None


class QueryRequest(BaseModel):
    message: str
    thread_id: str
    filters: Optional[QueryFilters] = None


class SourceDoc(BaseModel):
    file_name: str
    chunk_index: int
    score: float
    text: str
    category: str


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceDoc]
    thought_process: list[str]
    blocked: bool


class BlockedResponse(BaseModel):
    blocked: bool
    reason: str
    answer: str


# ── App factory ───────────────────────────────────────────────────────────────


def create_app() -> FastAPI:
    app = FastAPI(
        title="Banking Knowledge Intelligence Platform",
        description="Enterprise RAG API for banking compliance and policy queries",
        version="0.5.0",
        lifespan=lifespan,
    )

    # ── Instrument FastAPI with Logfire ───────────────────────────────────────
    # instrument_fastapi must be called after the app object is created.
    logfire.instrument_fastapi(app, capture_headers=False)

    # ── GET /health ───────────────────────────────────────────────────────────

    @app.get("/health", tags=["ops"])
    async def health() -> dict[str, Any]:
        """Return service, Qdrant, and observability status."""
        settings = get_settings()
        qdrant_status = check_qdrant_health()
        return {
            "status": "ok",
            "qdrant": qdrant_status,
            "version": "0.5.0",
            "gateway": "portkey" if settings.portkey_api_key else "direct_groq",
            "logfire": "active" if settings.logfire_token else "inactive",
            "langsmith": "active" if bool(_ls_key and _ls_tracing) else "inactive",
        }

    # ── POST /query ───────────────────────────────────────────────────────────

    @app.post("/query", tags=["rag"], response_model=Any)
    async def query(request: QueryRequest):
        """Run the RAG agent pipeline on the user's message.

        Flow:
          1. Guard check (Phase 4 RAIL_INDICATORS + LLM gate).
          2. Invoke LangGraph: Planner → [Retriever →] Responder.
          3. Return answer, sources, thought_process, blocked=False.
        """
        with logfire.span(
            "bkip.query",
            thread_id=request.thread_id,
            message_len=len(request.message),
        ):
            # Gate 1: guardrails
            guard_result = guard(request.message)
            if not guard_result.allowed:
                logger.warning(
                    "Request blocked | reason=%s thread_id=%s latency=%.1fms",
                    guard_result.reason,
                    request.thread_id,
                    guard_result.latency_ms,
                )
                logfire.info(
                    "guardrail.blocked",
                    reason=guard_result.reason,
                    thread_id=request.thread_id,
                )
                return BlockedResponse(
                    blocked=True,
                    reason=guard_result.reason or "policy_violation",
                    answer=guard_result.message or "This request cannot be processed.",
                )

            # Build initial agent state.
            filters_dict: Optional[dict[str, Optional[str]]] = None
            if request.filters:
                filters_dict = {
                    "category": request.filters.category,
                    "file_name": request.filters.file_name,
                }

            initial_state = {
                "messages": [HumanMessage(content=request.message)],
                "query": request.message,
                "documents": [],
                "intent": "",
                "thought_process": [],
                "thread_id": request.thread_id,
                "filters": filters_dict,
            }

            config = {"configurable": {"thread_id": request.thread_id}}

            graph = get_graph()
            try:
                with logfire.span("bkip.agent.invoke", thread_id=request.thread_id):
                    final_state = graph.invoke(initial_state, config=config)
            except Exception as exc:
                logger.exception("Agent graph error: %s", exc)
                raise HTTPException(status_code=500, detail=f"Agent error: {exc}") from exc

            # Extract the last AIMessage content as the answer.
            messages = final_state.get("messages", [])
            answer = ""
            for msg in reversed(messages):
                if hasattr(msg, "content") and not isinstance(msg, HumanMessage):
                    answer = msg.content
                    break

            raw_docs: list[dict] = final_state.get("documents", [])
            sources = [
                SourceDoc(
                    file_name=doc.get("file_name", ""),
                    chunk_index=doc.get("chunk_index", 0),
                    score=round(doc.get("score", 0.0), 4),
                    text=doc.get("text", ""),
                    category=doc.get("category", ""),
                )
                for doc in raw_docs
            ]

            intent = final_state.get("intent", "")
            logfire.info(
                "bkip.query.complete",
                intent=intent,
                sources_count=len(sources),
                answer_len=len(answer),
                thread_id=request.thread_id,
            )

            return QueryResponse(
                answer=answer,
                sources=sources,
                thought_process=final_state.get("thought_process", []),
                blocked=False,
            )

    return app


app = create_app()
