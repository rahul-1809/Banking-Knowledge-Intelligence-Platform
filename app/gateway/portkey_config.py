"""Portkey Gateway configuration builder.

Constructs Portkey Config dictionaries supporting:
- Fallbacks: Llama 3.3 70B (Primary) -> Llama 3.1 8B (Fallback)
- Automatic Retries: Exponential backoff on status codes [429, 500, 502, 503, 504]
- Request Timeouts: 30s timeout on 70B, 15s on 8B; 408 code triggers fallback
- Caching: Simple cache with configurable TTL (e.g. 1h for Planner, 30m for Guardrails)
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict, Optional

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

PRIMARY_MODEL = "llama-3.3-70b-versatile"
GUARD_MODEL = "llama-3.1-8b-instant"


@lru_cache(maxsize=16)
def get_portkey_config(
    mode: str = "primary",
    cache_ttl: Optional[int] = None,
) -> Dict[str, Any]:
    """Build and return a Portkey gateway config dictionary.

    Args:
        mode: Config strategy mode ("primary", "planner", "guardrail", "responder").
        cache_ttl: Optional cache expiration in seconds for simple caching.

    Returns:
        Dict representing the Portkey config object.
    """
    settings = get_settings()
    groq_primary_key = settings.groq_api_key
    groq_fallback_key = settings.groq_fallback_api_key or settings.groq_api_key

    targets = [
        {
            "provider": "groq",
            "api_key": groq_primary_key,
            "override_params": {"model": PRIMARY_MODEL},
            "request_timeout": 30000,
        },
        {
            "provider": "groq",
            "api_key": groq_fallback_key,
            "override_params": {"model": GUARD_MODEL},
            "request_timeout": 15000,
        },
    ]

    # For guardrail mode, use lightweight 8B model target directly
    if mode == "guardrail":
        targets = [
            {
                "provider": "groq",
                "api_key": groq_fallback_key,
                "override_params": {"model": GUARD_MODEL},
                "request_timeout": 15000,
            }
        ]

    config: Dict[str, Any] = {
        "strategy": {
            "mode": "fallback",
            "on_status_codes": [429, 500, 502, 503, 504, 408],
        },
        "retry": {
            "attempts": 3,
            "on_status_codes": [429, 500, 502, 503, 504],
        },
        "targets": targets,
    }

    # Add simple caching if specified or mode demands it
    effective_ttl = cache_ttl
    if effective_ttl is None:
        if mode == "planner":
            effective_ttl = 3600  # 1 hour for intent classification
        elif mode == "guardrail":
            effective_ttl = 1800  # 30 minutes for guardrail checks

    if effective_ttl:
        config["cache"] = {
            "mode": "simple",
            "max_age": effective_ttl,
        }

    logger.debug("Generated Portkey config for mode='%s', cache_ttl=%s", mode, effective_ttl)
    return config
