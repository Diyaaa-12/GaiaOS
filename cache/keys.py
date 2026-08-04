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

    @staticmethod
    def event_channel_key(investigation_id: str) -> str:
        """Return a namespaced key for pub/sub stream events.

        Example: ``gaiaos:events:550e8400-e29b-41d4-a716-446655440000``
        """
        return f"gaiaos:events:{investigation_id}"

    @staticmethod
    def station_key(lat: float, lon: float, network: str = "noaa") -> str:
        """Return a namespaced key for cached nearest station lookups by rounded coordinates.

        Rounding coordinates to 2 decimal places provides ~1.11 km spatial resolution
        at the equator, balancing cache key reuse vs geographic accuracy.

        Example: ``gaiaos:cache:station:noaa:35.68:139.65``
        """
        rounded_lat = round(lat, 2)
        rounded_lon = round(lon, 2)
        return f"gaiaos:cache:station:{network}:{rounded_lat}:{rounded_lon}"

    @staticmethod
    def circuit_key(source: str) -> str:
        """Return a namespaced key for per-source circuit-breaker state.

        Stores JSON-serialised state (status, failure_count, opened_at).
        Shared across all worker replicas via Redis.

        Example: ``gaiaos:circuit:noaa``
        """
        return f"gaiaos:circuit:{source}"

    @staticmethod
    def source_cache_key(source: str, key: str) -> str:
        """Return a namespaced key for resilience-layer per-source response caching.

        Distinct from the generic ``cache_key`` to make the source dimension explicit
        and to avoid collisions between tool-client cache entries and other cache uses.

        Example: ``gaiaos:cache:noaa:water_temperature:8723214``
        """
        return f"gaiaos:cache:{source}:{key}"

    @staticmethod
    def boundary_key(lat: float, lon: float) -> str:
        """Return a namespaced key for cached administrative boundary lookups.

        Rounding to 3 decimal places (~111 m spatial precision at the equator) accurately
        differentiates boundaries near municipal/regional borders while allowing cache reuse.

        Example: ``gaiaos:cache:boundary:48.857:2.352``
        """
        rounded_lat = round(lat, 3)
        rounded_lon = round(lon, 3)
        return f"gaiaos:cache:boundary:{rounded_lat}:{rounded_lon}"


