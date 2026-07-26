"""Retriever node — two-stage retrieval: Qdrant top-15 → FlashRank top-5.

Phase 2: raw Qdrant top-K passed directly to Responder.
Phase 3 (this file): FlashRank cross-encoder reranking inserted between
  Qdrant retrieval and the Responder.  On reranker failure the node falls
  back transparently to raw Qdrant ordering so retrieval never hard-fails.
Phase 5: Logfire spans for each retrieval stage with full attribute recording.
"""

from __future__ import annotations

from typing import Optional

import logfire

from app.agents.state import AgentState
from app.core.logging import get_logger
from app.services.retrieval.ranking_service import RERANKER_TOP_N, rerank
from app.services.retrieval.vector_store import DEFAULT_TOP_K, retrieve

logger = get_logger(__name__)


def retriever_node(state: AgentState) -> dict:
    """Two-stage retrieval node.

    Stage 1 — Vector search
        Embeds the query and fetches top-K=15 candidate chunks from Qdrant.
        Optional metadata filters (``category``, ``file_name``) are applied
        at this stage via the Qdrant payload filter API.

    Stage 2 — Reranking
        Passes the candidates and query to FlashRank (``ms-marco-MiniLM-L-6-v2``).
        Returns the top-5 highest cross-encoder-scored chunks.
        Falls back to raw Qdrant order if FlashRank is unavailable or errors.

    Phase 5: Logfire outer span + inner stage spans with full metrics.
    """
    query = state.get("query", "")
    thought_process = list(state.get("thought_process", []))
    filters: Optional[dict] = state.get("filters") or {}

    category = filters.get("category") if filters else None
    file_name = filters.get("file_name") if filters else None

    with logfire.span(
        "agent.retriever",
        query_preview=query[:80],
        top_k=DEFAULT_TOP_K,
        category_filter=category or "none",
        file_filter=file_name or "none",
    ):
        # ── Stage 1: Qdrant vector search ────────────────────────────────────
        logger.info(
            "Retriever Stage 1 — Qdrant top-%s for query=%r (category=%s, file_name=%s)",
            DEFAULT_TOP_K,
            query[:80],
            category,
            file_name,
        )

        with logfire.span(
            "retriever.qdrant_search",
            top_k=DEFAULT_TOP_K,
            category=category or "none",
            file_name=file_name or "none",
        ):
            raw_documents = retrieve(
                query=query,
                top_k=DEFAULT_TOP_K,
                category=category,
                file_name=file_name,
            )
            logfire.info(
                "retriever.qdrant_search.complete",
                results_count=len(raw_documents),
            )

        thought_process.append(
            f"[Retriever] Stage 1: Qdrant returned {len(raw_documents)} candidate chunks"
            + (f" (category={category})" if category else "")
            + (f" (file_name={file_name})" if file_name else "")
        )

        if not raw_documents:
            logger.warning("Retriever: no documents returned from Qdrant.")
            thought_process.append("[Retriever] No documents found — skipping reranking.")
            logfire.warn("retriever.no_results", query_preview=query[:80])
            return {"documents": [], "thought_process": thought_process}

        # ── Stage 2: FlashRank reranking ──────────────────────────────────────
        logger.info(
            "Retriever Stage 2 — FlashRank reranking %s candidates → top-%s",
            len(raw_documents),
            RERANKER_TOP_N,
        )

        with logfire.span(
            "retriever.flashrank_rerank",
            input_count=len(raw_documents),
            top_n=RERANKER_TOP_N,
        ):
            reranked_documents, reranker_used = rerank(
                query=query,
                documents=raw_documents,
                top_n=RERANKER_TOP_N,
            )
            logfire.info(
                "retriever.flashrank_rerank.complete",
                output_count=len(reranked_documents),
                reranker_used=reranker_used,
            )

        if reranker_used:
            thought_process.append(
                f"[Retriever] Stage 2: FlashRank reranked to top-{len(reranked_documents)} chunks."
            )
        else:
            thought_process.append(
                f"[Retriever] Stage 2: Reranker unavailable — using raw Qdrant top-{len(reranked_documents)}."
            )

        logger.info(
            "Retriever complete: %s raw → %s final chunks (reranker_used=%s)",
            len(raw_documents),
            len(reranked_documents),
            reranker_used,
        )

        logfire.info(
            "agent.retriever.complete",
            raw_count=len(raw_documents),
            final_count=len(reranked_documents),
            reranker_used=reranker_used,
        )

    return {
        "documents": reranked_documents,
        "thought_process": thought_process,
    }
