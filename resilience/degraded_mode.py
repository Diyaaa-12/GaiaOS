"""Degraded-mode contract for GaiaOS external tool calls (Phase 6 Milestone 1).

Public API
----------
``ResilientResult[T]``
    Typed result wrapper carrying the value, a degraded flag, and a source-status
    literal so callers know exactly what they got.

``resilient_call(source, fn, cache_key, ttl)``
    The single entry point for every external tool call.  Implements:
    1. Circuit-breaker check (skip live attempt if open).
    2. Retry with exponential backoff (max 3 attempts, jitter).
    3. On success: cache the result, return live result.
    4. On exhaustion: record failure, check cache, return cached/unavailable.

Data flow (from roadmap §12):
    Agent → tool client → resilient_call(source, fn, cache_key)
        → try fn() with retry
        → on exhaustion, check circuit
        → if open, serve cache (degraded=True)
        → if no cache and no live, source_status="unavailable"

Per-source TTL table
--------------------
TTLs are set conservatively — data that stales faster gets shorter TTLs.
Administrative / geocoding data is very stable and gets a long TTL.
These are named constants, not magic numbers.

Rollback
--------
Set ``RESILIENCE_BYPASS=true`` in environment to revert to bare Phase 5 behaviour
(no retry, no circuit breaker, no cache fallback) — dev/test only.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal, TypeVar

import httpx
from tenacity import RetryError

from cache.client import get_redis
from cache.keys import RedisKeyBuilder
from config.settings import get_settings
from logging_config import get_logger
from resilience import circuit_breaker
from resilience.retry_policy import with_retry

_log = get_logger(__name__)

T = TypeVar("T")

# ---------------------------------------------------------------------------
# Per-source TTL constants (seconds)
# ---------------------------------------------------------------------------
# Rationale: weather/wildfire data is real-time and stales fast; seismic and
# ocean data are updated hourly; geocoding / OSM data is quasi-permanent.
TTL_BY_SOURCE: dict[str, int] = {
    "usgs": 600,         # 10 min  — USGS seismic feeds update frequently
    "noaa": 900,         # 15 min  — NOAA water temperature / ocean readings
    "open_meteo": 300,   # 5 min   — Weather / atmospheric data is highly time-sensitive
    "firms": 300,        # 5 min   — Active fire data should be as fresh as possible
    "openaq": 600,       # 10 min  — Air-quality measurements update hourly at most
    "geocoding": 86400,  # 24 h    — Geocoded city coordinates change essentially never
    "copernicus": 1800,  # 30 min  — Copernicus Sentinel satellite metadata
    "era5": 3600,        # 1 h     — ERA5 atmospheric reanalysis baseline data
    "gdelt": 900,        # 15 min  — GDELT socio-political hazard news events
}

# Default for any source not in the table
_DEFAULT_TTL: int = 600


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------
@dataclass
class ResilientResult[T]:
    """Typed result from ``resilient_call``.

    Attributes:
        value: The unwrapped response value, or ``None`` when unavailable.
        degraded: True when the value is stale (cached) or absent (unavailable).
        source_status: ``"live"`` | ``"cached"`` | ``"unavailable"``.
    """

    value: T | None
    degraded: bool
    source_status: Literal["live", "cached", "unavailable"]


# ---------------------------------------------------------------------------
# Core function
# ---------------------------------------------------------------------------
async def resilient_call[T](
    source: str,
    fn: Callable[[], Awaitable[T]],
    cache_key: str,
    ttl: int | None = None,
) -> ResilientResult[T]:
    """Execute an external call with retry, circuit breaking, and cache fallback.

    Args:
        source:    Logical source name (``"noaa"``, ``"usgs"``, …) — used as the
                   circuit-breaker key and the cache-key namespace.
        fn:        Zero-argument async callable wrapping the HTTP call.
                   Must raise ``httpx.HTTPError`` (or a subclass) on failure
                   so the retry policy can detect it.
        cache_key: Discriminator string for this specific query (e.g. station ID,
                   bounding-box hash).  Combined with ``source`` via
                   ``RedisKeyBuilder.source_cache_key`` to avoid collisions.
        ttl:       Override TTL in seconds.  Defaults to ``TTL_BY_SOURCE[source]``
                   or ``_DEFAULT_TTL`` if the source is not in the table.

    Returns:
        ``ResilientResult`` — always returns, never raises to the caller.
    """
    settings = get_settings()

    # ------------------------------------------------------------------
    # Bypass path (dev/test rollback)
    # ------------------------------------------------------------------
    if settings.resilience_bypass:
        _log.debug("resilience.bypass_active", source=source)
        value = await fn()
        return ResilientResult(value=value, degraded=False, source_status="live")

    effective_ttl = ttl if ttl is not None else TTL_BY_SOURCE.get(source, _DEFAULT_TTL)
    redis_cache_key = RedisKeyBuilder.source_cache_key(source, cache_key)

    # ------------------------------------------------------------------
    # Circuit open? — skip live attempt, go straight to cache
    # ------------------------------------------------------------------
    if await circuit_breaker.is_open(source):
        _log.info("resilience.circuit_open_skip_live", source=source)
        return await _serve_from_cache(source, redis_cache_key)

    # ------------------------------------------------------------------
    # Attempt live call with retry
    # ------------------------------------------------------------------
    try:
        wrapped = with_retry(fn)
        value = await wrapped()

        # Success — cache the result and close/reset breaker
        await _cache_result(redis_cache_key, value, effective_ttl)
        await circuit_breaker.record_success(source)
        _log.info("resilience.live_success", source=source, cache_key=cache_key)
        return ResilientResult(value=value, degraded=False, source_status="live")

    except (httpx.HTTPError, RetryError) as exc:
        _log.warning(
            "resilience.live_exhausted",
            source=source,
            cache_key=cache_key,
            error=str(exc),
        )
        await circuit_breaker.record_failure(source)
        return await _serve_from_cache(source, redis_cache_key)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _cache_result(redis_cache_key: str, value: object, ttl: int) -> None:
    """Serialise and store a result in Redis with the given TTL."""
    try:
        redis = await get_redis()
        await redis.set(redis_cache_key, json.dumps(value), ex=ttl)
    except Exception as exc:
        # Cache write failures are non-fatal — log and continue
        _log.warning("resilience.cache_write_failed", key=redis_cache_key, error=str(exc))


async def _serve_from_cache(source: str, redis_cache_key: str) -> ResilientResult:
    """Try to serve a stale cached result; return unavailable if no cache exists."""
    try:
        redis = await get_redis()
        raw = await redis.get(redis_cache_key)
        if raw is not None:
            cached_value = json.loads(raw)
            _log.info(
                "resilience.cache_hit_degraded",
                source=source,
                key=redis_cache_key,
            )
            return ResilientResult(
                value=cached_value,
                degraded=True,
                source_status="cached",
            )
    except Exception as exc:
        _log.warning("resilience.cache_read_failed", key=redis_cache_key, error=str(exc))

    _log.warning("resilience.source_unavailable", source=source, key=redis_cache_key)
    return ResilientResult(value=None, degraded=True, source_status="unavailable")
