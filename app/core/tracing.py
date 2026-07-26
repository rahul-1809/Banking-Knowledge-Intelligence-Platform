"""Central tracing helpers for BKIP — Phase 5.

Provides:
  - get_langsmith_callbacks(): Returns LangChainTracer list when LANGSMITH_API_KEY
    is set, else empty list.  Wire into every llm.invoke() call as ``callbacks=``.
  - logfire: re-exported so nodes only need ``from app.core.tracing import logfire``
    instead of importing it directly (avoids multiple configure() calls).
"""

from __future__ import annotations

import os
from typing import Any

import logfire  # noqa: F401  — re-exported

from app.core.logging import get_logger

logger = get_logger(__name__)

# Cache the tracer list so we don't re-instantiate on every LLM call.
_callbacks_cache: list[Any] | None = None


def get_langsmith_callbacks() -> list[Any]:
    """Return ``[LangChainTracer()]`` when LangSmith credentials are configured.

    Supports both env-var conventions used by different LangChain versions:
      - LANGCHAIN_API_KEY  + LANGCHAIN_TRACING_V2=true  (older)
      - LANGSMITH_API_KEY  + LANGSMITH_TRACING=true      (newer)

    Returns an empty list when no credentials are found so callers can
    unconditionally pass ``callbacks=get_langsmith_callbacks()`` without
    any conditional logic.
    """
    global _callbacks_cache  # noqa: PLW0603
    if _callbacks_cache is not None:
        return _callbacks_cache

    api_key = os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY", "")
    tracing_v2 = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
    langsmith_tracing = os.getenv("LANGSMITH_TRACING", "false").lower() == "true"
    project = (os.getenv("LANGSMITH_PROJECT") or os.getenv("LANGCHAIN_PROJECT", "bkip")).strip('"\'')

    if api_key and (tracing_v2 or langsmith_tracing):
        try:
            os.environ["LANGCHAIN_TRACING_V2"] = "true"
            os.environ["LANGCHAIN_API_KEY"] = api_key
            os.environ["LANGCHAIN_PROJECT"] = project
            os.environ["LANGSMITH_TRACING"] = "true"
            os.environ["LANGSMITH_API_KEY"] = api_key
            os.environ["LANGSMITH_PROJECT"] = project

            from langsmith import Client  # type: ignore[import-untyped]
            from langchain_core.tracers import LangChainTracer  # type: ignore[import-untyped]

            tracer = LangChainTracer(project_name=project, client=Client(api_key=api_key))
            _callbacks_cache = [tracer]
            logger.info("LangSmith tracing enabled — project=%s", project)
        except Exception as exc:  # noqa: BLE001
            logger.warning("LangSmith tracer init failed (%s) — tracing disabled.", exc)
            _callbacks_cache = []
    else:
        if not api_key:
            logger.debug("LangSmith: no API key found — tracing disabled.")
        _callbacks_cache = []

    return _callbacks_cache
