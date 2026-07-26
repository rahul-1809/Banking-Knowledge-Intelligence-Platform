"""LLM client abstraction — Phase 5 & 6: Portkey gateway & resilient fallback.

Gateway selection & High Availability:

    - Primary model:  llama-3.3-70b-versatile (GROQ_API_KEY) — max_retries=0 for instant fallback
    - Fallback model: llama-3.1-8b-instant    (GROQ_FALLBACK_API_KEY or GROQ_API_KEY)

When the 70B model encounters a 429 rate limit (TPD / TPM quota limit) or network error,
LangChain's ``.with_fallbacks()`` instantly promotes the 8B instant model so
queries and evaluations succeed without delays or 500 errors.
"""

from __future__ import annotations

from functools import lru_cache

from langchain_core.language_models.chat_models import BaseChatModel

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Primary model: complex reasoning — Planner and Responder nodes.
PRIMARY_MODEL = "llama-3.3-70b-versatile"

# Guard/fallback model: fast inference — Guardrail gate and automatic fallback.
GUARD_MODEL = "llama-3.1-8b-instant"


def _build_direct_groq_llm(model: str, api_key: str, temperature: float, max_retries: int = 2) -> BaseChatModel:
    """Return a ChatGroq instance talking directly to Groq."""
    from langchain_groq import ChatGroq  # type: ignore[import-untyped]

    if not api_key:
        settings = get_settings()
        api_key = settings.groq_api_key

    if not api_key:
        raise ValueError("GROQ_API_KEY must be set in the environment.")

    logger.info("Building direct ChatGroq LLM — model=%s temperature=%s retries=%d", model, temperature, max_retries)
    return ChatGroq(
        model=model,
        api_key=api_key,
        temperature=temperature,
        max_retries=max_retries,
    )


@lru_cache(maxsize=8)
def get_llm(model: str = PRIMARY_MODEL, temperature: float = 0.0) -> BaseChatModel:
    """Return a resilient ChatModel with instant 70B -> 8B fallback.

    If the primary model hits Groq rate limits (429 TPD/TPM), it instantly falls
    back to the 8B instant model without waiting on retries.
    """
    settings = get_settings()

    primary_key = settings.groq_api_key
    fallback_key = settings.groq_fallback_api_key or settings.groq_api_key

    # max_retries=0 on primary ensures 429 immediately triggers the fallback model
    primary_llm = _build_direct_groq_llm(model=model, api_key=primary_key, temperature=temperature, max_retries=0)
    fallback_llm = _build_direct_groq_llm(model=GUARD_MODEL, api_key=fallback_key, temperature=temperature, max_retries=2)

    logger.info("Configuring LLM with instant 70B -> 8B fallback chain")
    return primary_llm.with_fallbacks([fallback_llm])


def get_primary_llm() -> BaseChatModel:
    """Convenience accessor for the primary 70B model with instant 8B fallback."""
    return get_llm(model=PRIMARY_MODEL, temperature=0.0)


def get_guard_llm() -> BaseChatModel:
    """Convenience accessor for the lightweight 8B guard model."""
    settings = get_settings()
    fallback_key = settings.groq_fallback_api_key or settings.groq_api_key
    return _build_direct_groq_llm(model=GUARD_MODEL, api_key=fallback_key, temperature=0.0, max_retries=2)
