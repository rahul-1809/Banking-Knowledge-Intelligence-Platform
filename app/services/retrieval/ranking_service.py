"""FlashRank reranker service — local CPU ONNX cross-encoder for two-stage retrieval.

Stage 1: Qdrant returns top-K=15 candidates by vector similarity.
Stage 2: FlashRank scores each candidate against the query and keeps top-5.

On any FlashRank error (OOM, model load failure, etc.) the service falls back
to the raw Qdrant ordering so retrieval never hard-fails.
"""

from __future__ import annotations

import threading
from typing import Optional

from app.core.logging import get_logger

logger = get_logger(__name__)

# Default FlashRank model — best CPU ONNX cross-encoder (~34 MB).
# flashrank supports: ms-marco-TinyBERT-L-2-v2 (default/nano, 4MB),
#   ms-marco-MiniLM-L-12-v2 (best precision), rank-T5-flan (110MB).
DEFAULT_RERANKER_MODEL = "ms-marco-MiniLM-L-12-v2"

# How many chunks to keep after reranking (post-reranker top-K).
RERANKER_TOP_N = 5

# Thread-safe lazy singleton.
_reranker_lock = threading.Lock()
_reranker_instance = None


def _get_reranker():
    """Lazily load the FlashRank Ranker and cache it as a module-level singleton.

    Thread-safe: uses a lock so concurrent first-calls don't double-load.
    Returns ``None`` on import / load failure so callers can fall back gracefully.
    """
    global _reranker_instance  # noqa: PLW0603
    if _reranker_instance is not None:
        return _reranker_instance

    with _reranker_lock:
        # Double-checked locking pattern.
        if _reranker_instance is not None:
            return _reranker_instance
        try:
            from flashrank import Ranker  # type: ignore[import-untyped]

            logger.info("Loading FlashRank reranker model: %s", DEFAULT_RERANKER_MODEL)
            _reranker_instance = Ranker(model_name=DEFAULT_RERANKER_MODEL)
            logger.info("FlashRank reranker loaded successfully.")
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "FlashRank reranker could not be loaded (%s). "
                "Retrieval will fall back to raw Qdrant scores.",
                exc,
            )
            _reranker_instance = None  # type: ignore[assignment]

    return _reranker_instance


def rerank(
    query: str,
    documents: list[dict],
    top_n: int = RERANKER_TOP_N,
) -> tuple[list[dict], bool]:
    """Rerank *documents* against *query* using FlashRank and return top-N.

    Parameters
    ----------
    query:
        The user query string.
    documents:
        List of document dicts as returned by :func:`vector_store.retrieve`.
        Each must contain at least a ``text`` key.
    top_n:
        Maximum number of documents to return after reranking.

    Returns
    -------
    tuple[list[dict], bool]
        * Reranked (and truncated) document list.
        * ``True`` if reranking succeeded, ``False`` if the fallback path was used.
    """
    if not documents:
        return [], True

    ranker = _get_reranker()
    if ranker is None:
        logger.warning("Reranker unavailable — using top-%s raw Qdrant results.", top_n)
        return documents[:top_n], False

    try:
        from flashrank import RerankRequest  # type: ignore[import-untyped]

        # Log raw ordering for Phase 6 comparison.
        raw_ids = [
            f"{d.get('doc_id', '?')}:{d.get('chunk_index', '?')}" for d in documents
        ]
        logger.debug("Reranker raw order (top-%s): %s", len(raw_ids), raw_ids[:5])

        passages = [{"id": i, "text": doc["text"]} for i, doc in enumerate(documents)]
        rerank_request = RerankRequest(query=query, passages=passages)
        results = ranker.rerank(rerank_request)

        # results is a list of dicts with keys: id, score, text.
        # Sort by score descending (FlashRank may already do this, but be explicit).
        results_sorted = sorted(results, key=lambda r: r.get("score", 0.0), reverse=True)
        top_results = results_sorted[:top_n]

        reranked_docs = []
        for r in top_results:
            original_doc = documents[r["id"]].copy()
            # Overwrite the score with the cross-encoder score for downstream display.
            original_doc["rerank_score"] = round(float(r.get("score", 0.0)), 6)
            reranked_docs.append(original_doc)

        reranked_ids = [
            f"{d.get('doc_id', '?')}:{d.get('chunk_index', '?')}" for d in reranked_docs
        ]
        logger.info(
            "Reranker: %s → %s chunks. Top reranked: %s",
            len(documents),
            len(reranked_docs),
            reranked_ids,
        )
        return reranked_docs, True

    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "FlashRank reranking failed (%s) — falling back to raw Qdrant top-%s.",
            exc,
            top_n,
        )
        return documents[:top_n], False


def is_reranker_available() -> bool:
    """Return ``True`` if the FlashRank model is loaded and ready."""
    return _get_reranker() is not None
