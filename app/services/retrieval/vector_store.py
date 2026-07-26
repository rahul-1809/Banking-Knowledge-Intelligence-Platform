"""Qdrant vector retriever — top-K similarity search with optional metadata filters.

Phase 5: Logfire span added to retrieve() for full retrieval latency tracking.
"""

from __future__ import annotations

import time
from functools import lru_cache
from typing import Optional

import logfire
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.retrieval.embedding import embed_query

logger = get_logger(__name__)

DEFAULT_TOP_K = 15


@lru_cache
def get_qdrant_client() -> QdrantClient:
    """Return a lazily initialised, cached Qdrant Cloud client."""
    settings = get_settings()
    if not settings.qdrant_cluster_endpoint or not settings.qdrant_api_key:
        raise ValueError(
            "QDRANT_CLUSTER_ENDPOINT and QDRANT_API_KEY must be set in the environment."
        )
    logger.info("Connecting to Qdrant at %s", settings.qdrant_cluster_endpoint)
    return QdrantClient(
        url=settings.qdrant_cluster_endpoint,
        api_key=settings.qdrant_api_key,
        timeout=60.0,
    )


def _build_filter(
    category: Optional[str] = None,
    file_name: Optional[str] = None,
) -> Optional[Filter]:
    """Compose a Qdrant filter from optional metadata constraints.

    Returns ``None`` when no filters are requested so Qdrant performs an
    unrestricted vector scan.
    """
    conditions = []
    if category:
        conditions.append(
            FieldCondition(key="category", match=MatchValue(value=category))
        )
    if file_name:
        conditions.append(
            FieldCondition(key="file_name", match=MatchValue(value=file_name))
        )
    if not conditions:
        return None
    return Filter(must=conditions)


def retrieve(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    category: Optional[str] = None,
    file_name: Optional[str] = None,
) -> list[dict]:
    """Search Qdrant and return ranked document chunks.

    Each returned dict contains:
        ``text``        – raw chunk text
        ``file_name``   – source document filename
        ``chunk_index`` – zero-based position inside the source document
        ``category``    – document category tag
        ``doc_id``      – unique document identifier
        ``score``       – cosine similarity score from Qdrant

    Phase 5: Logfire span records embedding + query latencies separately.
    """
    with logfire.span(
        "vector_store.retrieve",
        query_preview=query[:80],
        top_k=top_k,
        category=category or "none",
        file_name=file_name or "none",
    ):
        settings = get_settings()
        client = get_qdrant_client()

        # Embed the query and measure embedding latency.
        t_embed = time.perf_counter()
        vector = embed_query(query)
        embed_ms = round((time.perf_counter() - t_embed) * 1000, 1)

        query_filter = _build_filter(category=category, file_name=file_name)

        results = []
        max_retries = 3
        t_query = time.perf_counter()
        for attempt in range(max_retries):
            try:
                results = client.query_points(
                    collection_name=settings.qdrant_collection_name,
                    query=vector,
                    limit=top_k,
                    query_filter=query_filter,
                    with_payload=True,
                ).points
                break
            except Exception as exc:  # noqa: BLE001
                if attempt == max_retries - 1:
                    logger.error("Qdrant query_points failed after %d attempts: %s", max_retries, exc)
                    logfire.error("vector_store.qdrant_error", error=str(exc), attempts=max_retries)
                    return []
                import time as _time
                logger.warning("Qdrant query_points attempt %d failed (%s), retrying...", attempt + 1, exc)
                _time.sleep(1.0 * (attempt + 1))

        query_ms = round((time.perf_counter() - t_query) * 1000, 1)

        documents = []
        for hit in results:
            payload = hit.payload or {}
            documents.append(
                {
                    "text": payload.get("text", ""),
                    "file_name": payload.get("file_name", ""),
                    "chunk_index": payload.get("chunk_index", 0),
                    "category": payload.get("category", ""),
                    "doc_id": payload.get("doc_id", ""),
                    "score": hit.score,
                }
            )

        logger.debug(
            "Retrieved %s chunks for query=%r (category=%s, file_name=%s)",
            len(documents),
            query[:60],
            category,
            file_name,
        )
        logfire.info(
            "vector_store.retrieve.complete",
            results_count=len(documents),
            embed_latency_ms=embed_ms,
            qdrant_latency_ms=query_ms,
            category=category or "none",
        )

    return documents


def ensure_payload_indexes() -> None:
    """Create keyword payload indexes for filterable fields if they don't exist.

    Safe to call on an existing collection — Qdrant silently ignores duplicate
    index creation attempts (we catch any exception).  Called at health-check
    time so filters work immediately without a full re-ingest.
    """
    try:
        from qdrant_client.models import PayloadSchemaType

        settings = get_settings()
        client = get_qdrant_client()
        for field in ("category", "file_name", "doc_id"):
            try:
                client.create_payload_index(
                    collection_name=settings.qdrant_collection_name,
                    field_name=field,
                    field_schema=PayloadSchemaType.KEYWORD,
                )
            except Exception:  # noqa: BLE001
                pass  # already exists
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not ensure payload indexes: %s", exc)


def check_qdrant_health() -> str:
    """Return 'connected' or 'unavailable' for health-check reporting."""
    try:
        settings = get_settings()
        client = get_qdrant_client()
        client.get_collection(settings.qdrant_collection_name)
        # Bootstrap keyword indexes so metadata filters work immediately.
        ensure_payload_indexes()
        return "connected"
    except Exception as exc:  # noqa: BLE001
        logger.warning("Qdrant health check failed: %s", exc)
        return "unavailable"
