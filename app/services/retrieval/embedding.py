"""Embedding service — HuggingFace BGE-small-en-v1.5 sentence encoder.

Phase 5: Logfire spans added to embed_query() and embed_texts() to surface
model load time and per-call encoding latency in the Logfire dashboard.
"""

import time
from functools import lru_cache

import logfire
from langchain_huggingface import HuggingFaceEmbeddings

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@lru_cache
def get_embedding_model() -> HuggingFaceEmbeddings:
    settings = get_settings()
    logger.info("Loading embedding model: %s", settings.embedding_model)
    with logfire.span("embedding.model_load", model=settings.embedding_model):
        model = HuggingFaceEmbeddings(
            model_name=settings.embedding_model,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
    logger.info("Embedding model loaded: %s", settings.embedding_model)
    return model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of document texts.  Logfire span records batch size + latency."""
    if not texts:
        return []
    with logfire.span("embedding.encode_batch", count=len(texts)):
        t0 = time.perf_counter()
        model = get_embedding_model()
        vectors = model.embed_documents(texts)
        latency_ms = round((time.perf_counter() - t0) * 1000, 1)
        logfire.info("embedding.encode_batch.complete", count=len(texts), latency_ms=latency_ms)
    return vectors


def embed_query(text: str) -> list[float]:
    """Embed a single query string.  Logfire span records latency."""
    with logfire.span("embedding.encode_query", text_preview=text[:60]):
        t0 = time.perf_counter()
        model = get_embedding_model()
        vector = model.embed_query(text)
        latency_ms = round((time.perf_counter() - t0) * 1000, 1)
        logfire.info("embedding.encode_query.complete", latency_ms=latency_ms)
    return vector
