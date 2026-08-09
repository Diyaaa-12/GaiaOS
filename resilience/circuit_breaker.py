"""Redis-backed per-source circuit breaker (Phase 6 Milestone 1).

State machine per source:
  closed  → open      : N consecutive failures (``circuit_failure_threshold`` from Settings)
  open    → half-open : after ``circuit_half_open_timeout_s`` seconds
  half-open → closed  : on probe success (``record_success``)
  half-open → open    : on probe failure (``record_failure``)

State is stored in Redis as a JSON hash so it is shared correctly across all
horizontally-scaled worker replicas — a worker-local-only breaker would let
each replica independently hammer a down source.

Redis key: ``gaiaos:circuit:{source}``  (via ``RedisKeyBuilder.circuit_key``)
Value: JSON ``{"status": "closed"|"open"|"half-open", "failure_count": N, "opened_at": ISO|null}``

ADR-601: custom ~50-line Redis-backed breaker, not ``pybreaker``.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from cache.client import get_redis
from cache.keys import RedisKeyBuilder
from config.settings import get_settings
from logging_config import get_logger

_log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Status literals
# ---------------------------------------------------------------------------
CLOSED = "closed"
OPEN = "open"
HALF_OPEN = "half-open"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _parse_dt(iso: str | None) -> datetime | None:
    if iso is None:
        return None
    try:
        return datetime.fromisoformat(iso)
    except ValueError:
        return None


async def _get_state(source: str) -> dict:
    """Fetch current circuit state from Redis; returns closed/zero state on miss or error."""
    try:
        redis = await get_redis()
        key = RedisKeyBuilder.circuit_key(source)
        raw = await redis.get(key)
        if raw is None:
            return {"status": CLOSED, "failure_count": 0, "opened_at": None}
        try:
            return json.loads(raw)  # type: ignore[no-any-return]
        except (json.JSONDecodeError, TypeError):
            return {"status": CLOSED, "failure_count": 0, "opened_at": None}
    except Exception as exc:
        _log.warning(
            "circuit_breaker.redis_unavailable",
            source=source,
            error=str(exc),
        )
        return {"status": CLOSED, "failure_count": 0, "opened_at": None}


async def _set_state(source: str, state: dict) -> None:
    """Persist circuit state to Redis.  No TTL — state is permanent until reset.

    Silently ignores Redis unavailability — if state cannot be persisted, the
    circuit simply operates statelessly (always-closed) for this replica until
    Redis recovers.
    """
    try:
        redis = await get_redis()
        key = RedisKeyBuilder.circuit_key(source)
        await redis.set(key, json.dumps(state))
    except Exception as exc:
        _log.warning(
            "circuit_breaker.state_persist_failed",
            source=source,
            error=str(exc),
        )


async def is_open(source: str) -> bool:
    """Return True if the circuit is open *and* the half-open window has not elapsed.

    When the half-open window has elapsed the circuit transitions to half-open
    (allowing a single probe attempt) and this returns False so the caller proceeds.
    """
    settings = get_settings()
    state = await _get_state(source)

    if state["status"] == CLOSED:
        return False

    if state["status"] == HALF_OPEN:
        # Already in half-open; let the probe through
        return False

    # status == OPEN — check whether half-open window has elapsed
    opened_at = _parse_dt(state.get("opened_at"))
    if opened_at is None:
        # Corrupt state — treat as closed
        return False

    elapsed = (datetime.now(UTC) - opened_at).total_seconds()
    if elapsed >= settings.circuit_half_open_timeout_s:
        # Transition open → half-open
        state["status"] = HALF_OPEN
        await _set_state(source, state)
        _log.info(
            "circuit_breaker.transition",
            source=source,
            previous="open",
            current="half-open",
            elapsed_s=round(elapsed, 1),
        )
        return False  # probe allowed

    return True  # still open


async def record_failure(source: str) -> None:
    """Increment failure count; open circuit if threshold reached."""
    settings = get_settings()
    state = await _get_state(source)
    state["failure_count"] = state.get("failure_count", 0) + 1

    if state["status"] in (CLOSED, HALF_OPEN):
        if state["failure_count"] >= settings.circuit_failure_threshold:
            previous = state["status"]
            state["status"] = OPEN
            state["opened_at"] = _now_iso()
            await _set_state(source, state)
            _log.warning(
                "circuit_breaker.transition",
                source=source,
                previous=previous,
                current=OPEN,
                failure_count=state["failure_count"],
            )
        else:
            await _set_state(source, state)
    else:
        # Already open — just persist the updated count
        await _set_state(source, state)


async def record_success(source: str) -> None:
    """Reset circuit to closed and clear failure count on a successful probe."""
    state = await _get_state(source)
    previous = state["status"]
    failure_count = state.get("failure_count", 0)
    if previous != CLOSED or failure_count != 0:
        state = {"status": CLOSED, "failure_count": 0, "opened_at": None}
        await _set_state(source, state)
        if previous != CLOSED:
            _log.info(
                "circuit_breaker.transition",
                source=source,
                previous=previous,
                current=CLOSED,
            )


async def get_circuit_status(source: str) -> str:
    """Return current circuit status ("closed" | "open" | "half-open") for a source."""
    state = await _get_state(source)
    return str(state.get("status", CLOSED))


__all__ = [
    "CLOSED",
    "OPEN",
    "HALF_OPEN",
    "is_open",
    "record_failure",
    "record_success",
    "get_circuit_status",
]


