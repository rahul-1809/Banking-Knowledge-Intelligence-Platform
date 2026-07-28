"""LLM client abstraction — Portkey gateway & resilient fallback.

Gateway selection & High Availability:
    - Primary model:  llama-3.3-70b-versatile (GROQ_API_KEY)
    - Fallback model: llama-3.1-8b-instant    (GROQ_FALLBACK_API_KEY or GROQ_API_KEY)

Supports Portkey AI Gateway when PORTKEY_API_KEY and PORTKEY_CONFIG_ID are present.
If Portkey inline config is blocked or PORTKEY_CONFIG_ID is not configured, automatically
and gracefully falls back to direct ChatGroq with instant 70B -> 8B fallback chain.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from langchain_core.language_models.chat_models import BaseChatModel

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

PRIMARY_MODEL = "llama-3.3-70b-versatile"
GUARD_MODEL = "llama-3.1-8b-instant"


def _build_direct_groq_llm(
    model: str, api_key: str, temperature: float, max_retries: int = 2
) -> BaseChatModel:
    """Return a ChatGroq instance talking directly to Groq."""
    from langchain_groq import ChatGroq  # type: ignore[import-untyped]

    if not api_key:
        settings = get_settings()
        api_key = settings.groq_api_key

    if not api_key:
        raise ValueError("GROQ_API_KEY must be set in the environment.")

    logger.info(
        "Building direct ChatGroq LLM — model=%s temperature=%s retries=%d",
        model,
        temperature,
        max_retries,
    )
    return ChatGroq(
        model=model,
        api_key=api_key,
        temperature=temperature,
        max_retries=max_retries,
    )


def _build_direct_fallback_chain(
    model: str = PRIMARY_MODEL, temperature: float = 0.0
) -> BaseChatModel:
    """Build direct ChatGroq fallback chain (70B primary -> 8B fallback)."""
    settings = get_settings()
    primary_key = settings.groq_api_key
    fallback_key = settings.groq_fallback_api_key or settings.groq_api_key

    primary_llm = _build_direct_groq_llm(
        model=model, api_key=primary_key, temperature=temperature, max_retries=0
    )
    fallback_llm = _build_direct_groq_llm(
        model=GUARD_MODEL, api_key=fallback_key, temperature=temperature, max_retries=2
    )

    logger.info("Configuring direct ChatGroq 70B -> 8B fallback chain")
    return primary_llm.with_fallbacks([fallback_llm])


def get_portkey_llm(
    mode: str = "primary",
    temperature: float = 0.0,
    metadata: Optional[Dict[str, Any]] = None,
) -> BaseChatModel:
    """Return a ChatModel routed through Portkey AI Gateway if configured, else direct Groq.

    If PORTKEY_API_KEY and PORTKEY_CONFIG_ID are present, routes through Portkey with metadata.
    Otherwise, uses direct ChatGroq fallback chain.
    """
    settings = get_settings()

    if not settings.portkey_api_key:
        logger.debug("PORTKEY_API_KEY not set — using direct ChatGroq fallback chain")
        return _build_direct_fallback_chain(model=PRIMARY_MODEL, temperature=temperature)

    if not settings.portkey_config_id:
        logger.info(
            "PORTKEY_CONFIG_ID not set; using direct Groq with resilient 70B->8B fallback chain"
        )
        return _build_direct_fallback_chain(model=PRIMARY_MODEL, temperature=temperature)

    try:
        from langchain_openai import ChatOpenAI
        from portkey_ai import PORTKEY_GATEWAY_URL, createHeaders

        header_kwargs: Dict[str, Any] = {
            "api_key": settings.portkey_api_key,
            "config": settings.portkey_config_id,
        }
        if metadata:
            header_kwargs["metadata"] = metadata

        headers = createHeaders(**header_kwargs)

        model_name = GUARD_MODEL if mode == "guardrail" else PRIMARY_MODEL
        groq_key = settings.groq_api_key

        logger.info(
            "Building Portkey ChatOpenAI client — config=%s mode=%s model=%s",
            settings.portkey_config_id,
            mode,
            model_name,
        )

        return ChatOpenAI(
            api_key=groq_key or "dummy-key",
            base_url=PORTKEY_GATEWAY_URL,
            default_headers=headers,
            model=model_name,
            temperature=temperature,
        )
    except Exception as exc:
        logger.warning(
            "Failed to initialize Portkey ChatOpenAI client (%s); falling back to direct Groq",
            exc,
        )
        return _build_direct_fallback_chain(model=PRIMARY_MODEL, temperature=temperature)


def get_llm(
    mode: str = "primary",
    temperature: float = 0.0,
    metadata: Optional[Dict[str, Any]] = None,
) -> BaseChatModel:
    """Main LLM accessor for agent nodes."""
    return get_portkey_llm(mode=mode, temperature=temperature, metadata=metadata)


def get_primary_llm(metadata: Optional[Dict[str, Any]] = None) -> BaseChatModel:
    """Convenience accessor for primary LLM."""
    return get_llm(mode="primary", temperature=0.0, metadata=metadata)


def get_planner_llm(metadata: Optional[Dict[str, Any]] = None) -> BaseChatModel:
    """Convenience accessor for Planner node."""
    return get_llm(mode="planner", temperature=0.0, metadata=metadata)


def get_guard_llm(metadata: Optional[Dict[str, Any]] = None) -> BaseChatModel:
    """Convenience accessor for Guardrail node."""
    return get_llm(mode="guardrail", temperature=0.0, metadata=metadata)


def get_responder_llm(metadata: Optional[Dict[str, Any]] = None) -> BaseChatModel:
    """Convenience accessor for Responder node."""
    return get_llm(mode="responder", temperature=0.0, metadata=metadata)
