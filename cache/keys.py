"""Centralised Redis key naming patterns.

Ensures namespaces like cache, checkpointing, and rate limiting are consistently
formatted across the application, preventing key collision bugs.
"""

from __future__ import annotations


class RedisKeyBuilder:
    """Helper to build standard, namespaced Redis keys for GaiaOS."""

    @staticmethod
    def cache_key(key: str) -> str:
        """Return a namespaced key for application caching.

        Example: ``gaiaos:cache:air_quality:beijing``
        """
        return f"gaiaos:cache:{key}"

    @staticmethod
    def checkpoint_key(thread_id: str) -> str:
        """Return a namespaced key for LangGraph state checkpointing.

        Example: ``gaiaos:checkpoint:550e8400-e29b-41d4-a716-446655440000``
        """
        return f"gaiaos:checkpoint:{thread_id}"

    @staticmethod
    def rate_limit_key(identifier: str, action: str) -> str:
        """Return a namespaced key for rate limiting.

        Example: ``gaiaos:ratelimit:192.168.1.1:create_investigation``
        """
        return f"gaiaos:ratelimit:{identifier}:{action}"
