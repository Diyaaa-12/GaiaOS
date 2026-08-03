"""Tests for the Phase 6 M1 resilience layer.

Root-cause rule
---------------
If a test fails, determine whether the *implementation* or the *test* is at
fault before changing either.  The failure message, the failing assertion, and
the implementation path under test must all be inspected together before any
edit is made.  A test that is simply inconvenient to pass is not a broken test.

Coverage
--------
Unit tests   (1–9)  — retry policy, circuit-breaker state machine, resilient_call
Integration  (10–11) — real tool client wrapped end-to-end with FakeRedis
Regression   (12)    — confirms existing agent tests still compile and import cleanly
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

# ---------------------------------------------------------------------------
# Helpers — inline FakeRedis shim (no fakeredis package required)
# ---------------------------------------------------------------------------

class _InMemoryRedis:
    """Minimal in-memory Redis shim for unit tests (no network, no docker)."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._store[key] = value

    async def ping(self) -> bool:
        return True

    def clear(self) -> None:
        self._store.clear()


def _make_redis() -> _InMemoryRedis:
    return _InMemoryRedis()


# ---------------------------------------------------------------------------
# Unit Test 1 — Retry policy: max 3 attempts on httpx.HTTPError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retry_policy_max_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that the tenacity policy retries exactly MAX_ATTEMPTS times."""
    from resilience.retry_policy import MAX_ATTEMPTS
    import resilience.retry_policy as rp
    from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_none

    # Replace the module-level retry policy with a no-wait version for speed
    no_wait_policy = retry(
        stop=stop_after_attempt(MAX_ATTEMPTS),
        wait=wait_none(),
        retry=retry_if_exception_type(httpx.HTTPError),
        reraise=True,
    )
    monkeypatch.setattr(rp, "_RETRY_POLICY", no_wait_policy)

    call_count = 0

    async def _flaky() -> None:
        nonlocal call_count
        call_count += 1
        raise httpx.NetworkError("simulated failure")

    with pytest.raises(httpx.NetworkError):
        wrapped = rp.with_retry(_flaky)
        await wrapped()

    assert call_count == MAX_ATTEMPTS, (
        f"Expected {MAX_ATTEMPTS} attempts, got {call_count}. "
        "Check retry_policy.MAX_ATTEMPTS and stop_after_attempt configuration."
    )


# ---------------------------------------------------------------------------
# Unit Test 2 — Circuit breaker: closed → open after threshold
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    """Circuit opens when consecutive failures reach circuit_failure_threshold."""
    from resilience import circuit_breaker

    fake_redis = _make_redis()
    monkeypatch.setattr("resilience.circuit_breaker.get_redis", AsyncMock(return_value=fake_redis))

    from config.settings import Settings
    mock_settings = MagicMock(spec=Settings)
    mock_settings.circuit_failure_threshold = 3
    mock_settings.circuit_half_open_timeout_s = 60
    monkeypatch.setattr("resilience.circuit_breaker.get_settings", lambda: mock_settings)

    source = "test_source_opens"

    # Should be closed initially
    assert not await circuit_breaker.is_open(source)

    # Fail N-1 times — should still be closed
    for _ in range(2):
        await circuit_breaker.record_failure(source)
    assert not await circuit_breaker.is_open(source)

    # Fail the Nth time — should open
    await circuit_breaker.record_failure(source)
    assert await circuit_breaker.is_open(source)


# ---------------------------------------------------------------------------
# Unit Test 3 — Circuit breaker: open → half-open after timeout
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_circuit_breaker_half_open_after_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Circuit transitions to half-open when the timeout window has elapsed."""
    from datetime import UTC, datetime, timedelta

    from resilience import circuit_breaker
    from cache.keys import RedisKeyBuilder

    fake_redis = _make_redis()
    monkeypatch.setattr("resilience.circuit_breaker.get_redis", AsyncMock(return_value=fake_redis))

    from config.settings import Settings
    mock_settings = MagicMock(spec=Settings)
    mock_settings.circuit_failure_threshold = 1
    mock_settings.circuit_half_open_timeout_s = 30
    monkeypatch.setattr("resilience.circuit_breaker.get_settings", lambda: mock_settings)

    source = "test_source_half_open"

    # Manually inject an open state that expired 60 seconds ago
    opened_at = (datetime.now(UTC) - timedelta(seconds=60)).isoformat()
    state = {"status": "open", "failure_count": 3, "opened_at": opened_at}
    key = RedisKeyBuilder.circuit_key(source)
    await fake_redis.set(key, json.dumps(state))

    # is_open should return False (transitions to half-open and allows probe)
    result = await circuit_breaker.is_open(source)
    assert result is False, "Expected half-open probe to be allowed after timeout."

    # State should now be half-open in Redis
    stored = json.loads(await fake_redis.get(key))
    assert stored["status"] == "half-open"


# ---------------------------------------------------------------------------
# Unit Test 4 — Circuit breaker: half-open → closed on success
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_circuit_breaker_closed_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Record_success from half-open resets to closed."""
    from resilience import circuit_breaker
    from cache.keys import RedisKeyBuilder

    fake_redis = _make_redis()
    monkeypatch.setattr("resilience.circuit_breaker.get_redis", AsyncMock(return_value=fake_redis))

    source = "test_source_success"
    # Inject half-open state
    key = RedisKeyBuilder.circuit_key(source)
    state = {"status": "half-open", "failure_count": 5, "opened_at": "2026-01-01T00:00:00+00:00"}
    await fake_redis.set(key, json.dumps(state))

    await circuit_breaker.record_success(source)

    stored = json.loads(await fake_redis.get(key))
    assert stored["status"] == "closed"
    assert stored["failure_count"] == 0


# ---------------------------------------------------------------------------
# Unit Test 5 — Circuit breaker: half-open → open on probe failure
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_circuit_breaker_reopens_on_probe_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Record_failure from half-open re-opens the circuit."""
    from resilience import circuit_breaker
    from cache.keys import RedisKeyBuilder

    fake_redis = _make_redis()
    monkeypatch.setattr("resilience.circuit_breaker.get_redis", AsyncMock(return_value=fake_redis))

    from config.settings import Settings
    mock_settings = MagicMock(spec=Settings)
    mock_settings.circuit_failure_threshold = 1  # threshold 1 so even one failure opens
    mock_settings.circuit_half_open_timeout_s = 60
    monkeypatch.setattr("resilience.circuit_breaker.get_settings", lambda: mock_settings)

    source = "test_source_probe_fail"
    key = RedisKeyBuilder.circuit_key(source)
    state = {"status": "half-open", "failure_count": 0, "opened_at": None}
    await fake_redis.set(key, json.dumps(state))

    await circuit_breaker.record_failure(source)

    stored = json.loads(await fake_redis.get(key))
    assert stored["status"] == "open", (
        "Expected circuit to re-open after probe failure from half-open state."
    )


# ---------------------------------------------------------------------------
# Unit Test 6 — resilient_call: happy path returns live result
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resilient_call_live_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """resilient_call returns live result and caches it on success."""
    fake_redis = _make_redis()
    monkeypatch.setattr("resilience.degraded_mode.get_redis", AsyncMock(return_value=fake_redis))
    monkeypatch.setattr(
        "resilience.circuit_breaker.get_redis", AsyncMock(return_value=fake_redis)
    )

    from config.settings import Settings
    mock_settings = MagicMock(spec=Settings)
    mock_settings.resilience_bypass = False
    mock_settings.circuit_failure_threshold = 5
    mock_settings.circuit_half_open_timeout_s = 60
    monkeypatch.setattr("resilience.degraded_mode.get_settings", lambda: mock_settings)
    monkeypatch.setattr("resilience.circuit_breaker.get_settings", lambda: mock_settings)

    expected = {"temperature": 25.0}

    async def _fn() -> dict:
        return expected

    from resilience.degraded_mode import resilient_call
    result = await resilient_call(source="noaa", fn=_fn, cache_key="test:live")

    assert result.degraded is False
    assert result.source_status == "live"
    assert result.value == expected

    # Verify result was cached
    from cache.keys import RedisKeyBuilder
    cached_raw = await fake_redis.get(RedisKeyBuilder.source_cache_key("noaa", "test:live"))
    assert cached_raw is not None
    assert json.loads(cached_raw) == expected


# ---------------------------------------------------------------------------
# Unit Test 7 — resilient_call: all retries fail → cache hit → degraded
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resilient_call_cache_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """When fn always fails, resilient_call falls back to cache with degraded=True."""
    from cache.keys import RedisKeyBuilder

    fake_redis = _make_redis()
    monkeypatch.setattr("resilience.degraded_mode.get_redis", AsyncMock(return_value=fake_redis))
    monkeypatch.setattr(
        "resilience.circuit_breaker.get_redis", AsyncMock(return_value=fake_redis)
    )

    from config.settings import Settings
    mock_settings = MagicMock(spec=Settings)
    mock_settings.resilience_bypass = False
    mock_settings.circuit_failure_threshold = 5
    mock_settings.circuit_half_open_timeout_s = 60
    monkeypatch.setattr("resilience.degraded_mode.get_settings", lambda: mock_settings)
    monkeypatch.setattr("resilience.circuit_breaker.get_settings", lambda: mock_settings)

    stale = {"temperature": 20.0, "_stale": True}
    cache_key = "test:cache_fallback"
    redis_key = RedisKeyBuilder.source_cache_key("noaa", cache_key)
    await fake_redis.set(redis_key, json.dumps(stale))

    call_count = 0

    async def _always_fail() -> dict:
        nonlocal call_count
        call_count += 1
        raise httpx.NetworkError("down")

    import resilience.retry_policy as rp
    from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_none
    no_wait = retry(
        stop=stop_after_attempt(rp.MAX_ATTEMPTS),
        wait=wait_none(),
        retry=retry_if_exception_type(httpx.HTTPError),
        reraise=True,
    )
    monkeypatch.setattr(rp, "_RETRY_POLICY", no_wait)

    from resilience.degraded_mode import resilient_call
    result = await resilient_call(source="noaa", fn=_always_fail, cache_key=cache_key)

    assert result.degraded is True
    assert result.source_status == "cached"
    assert result.value == stale


# ---------------------------------------------------------------------------
# Unit Test 8 — resilient_call: all retries fail, no cache → unavailable
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resilient_call_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    """When fn always fails and no cache exists, source_status='unavailable'."""
    fake_redis = _make_redis()
    monkeypatch.setattr("resilience.degraded_mode.get_redis", AsyncMock(return_value=fake_redis))
    monkeypatch.setattr(
        "resilience.circuit_breaker.get_redis", AsyncMock(return_value=fake_redis)
    )

    from config.settings import Settings
    mock_settings = MagicMock(spec=Settings)
    mock_settings.resilience_bypass = False
    mock_settings.circuit_failure_threshold = 5
    mock_settings.circuit_half_open_timeout_s = 60
    monkeypatch.setattr("resilience.degraded_mode.get_settings", lambda: mock_settings)
    monkeypatch.setattr("resilience.circuit_breaker.get_settings", lambda: mock_settings)

    async def _always_fail() -> dict:
        raise httpx.NetworkError("down")

    import resilience.retry_policy as rp
    from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_none
    no_wait = retry(
        stop=stop_after_attempt(rp.MAX_ATTEMPTS),
        wait=wait_none(),
        retry=retry_if_exception_type(httpx.HTTPError),
        reraise=True,
    )
    monkeypatch.setattr(rp, "_RETRY_POLICY", no_wait)

    from resilience.degraded_mode import resilient_call
    result = await resilient_call(source="noaa", fn=_always_fail, cache_key="test:unavailable")

    assert result.degraded is True
    assert result.source_status == "unavailable"
    assert result.value is None


# ---------------------------------------------------------------------------
# Unit Test 9 — resilient_call: circuit open → live call skipped
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resilient_call_skips_live_when_circuit_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the circuit is open, fn is never called."""
    from cache.keys import RedisKeyBuilder
    from datetime import UTC, datetime

    fake_redis = _make_redis()
    monkeypatch.setattr("resilience.degraded_mode.get_redis", AsyncMock(return_value=fake_redis))
    monkeypatch.setattr(
        "resilience.circuit_breaker.get_redis", AsyncMock(return_value=fake_redis)
    )

    from config.settings import Settings
    mock_settings = MagicMock(spec=Settings)
    mock_settings.resilience_bypass = False
    mock_settings.circuit_failure_threshold = 1
    mock_settings.circuit_half_open_timeout_s = 3600  # very long — won't expire
    monkeypatch.setattr("resilience.degraded_mode.get_settings", lambda: mock_settings)
    monkeypatch.setattr("resilience.circuit_breaker.get_settings", lambda: mock_settings)

    # Inject an open circuit that hasn't expired
    source = "noaa"
    key = RedisKeyBuilder.circuit_key(source)
    opened_at = datetime.now(UTC).isoformat()
    state = {"status": "open", "failure_count": 5, "opened_at": opened_at}
    await fake_redis.set(key, json.dumps(state))

    # Seed cache
    cache_key = "test:circuit_open"
    redis_key = RedisKeyBuilder.source_cache_key(source, cache_key)
    cached = {"temperature": 18.0}
    await fake_redis.set(redis_key, json.dumps(cached))

    fn_called = False

    async def _should_not_be_called() -> dict:
        nonlocal fn_called
        fn_called = True
        return {}

    from resilience.degraded_mode import resilient_call
    result = await resilient_call(source=source, fn=_should_not_be_called, cache_key=cache_key)

    assert fn_called is False, "fn must NOT be called when circuit is open"
    assert result.source_status == "cached"


# ---------------------------------------------------------------------------
# Integration Test 10 — NOAAOceanClient wrapped: 503 → cache fallback
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_noaa_client_cache_fallback_on_503(monkeypatch: pytest.MonkeyPatch) -> None:
    """NOAAOceanClient: all HTTP attempts return 503, cache is served instead."""
    import respx
    import httpx as _httpx
    from cache.keys import RedisKeyBuilder

    fake_redis = _make_redis()
    monkeypatch.setattr("resilience.degraded_mode.get_redis", AsyncMock(return_value=fake_redis))
    monkeypatch.setattr(
        "resilience.circuit_breaker.get_redis", AsyncMock(return_value=fake_redis)
    )

    from config.settings import Settings
    mock_settings = MagicMock(spec=Settings)
    mock_settings.resilience_bypass = False
    mock_settings.circuit_failure_threshold = 5
    mock_settings.circuit_half_open_timeout_s = 60
    mock_settings.noaa_api_url = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
    monkeypatch.setattr("resilience.degraded_mode.get_settings", lambda: mock_settings)
    monkeypatch.setattr("resilience.circuit_breaker.get_settings", lambda: mock_settings)
    monkeypatch.setattr("tools.ocean_noaa.client.get_settings", lambda: mock_settings)

    stale = {"data": [{"t": "2026-01-01 00:00", "v": "22.5"}]}
    cache_key = "water_temperature:8723214:latest"
    redis_key = RedisKeyBuilder.source_cache_key("noaa", cache_key)
    await fake_redis.set(redis_key, json.dumps(stale))

    from tools.ocean_noaa.client import NOAAOceanClient

    import resilience.retry_policy as rp
    from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_none
    no_wait = retry(
        stop=stop_after_attempt(rp.MAX_ATTEMPTS),
        wait=wait_none(),
        retry=retry_if_exception_type(httpx.HTTPError),
        reraise=True,
    )
    monkeypatch.setattr(rp, "_RETRY_POLICY", no_wait)

    with respx.mock:
        respx.get(mock_settings.noaa_api_url).mock(
            return_value=_httpx.Response(503, text="Service Unavailable")
        )
        client = NOAAOceanClient(base_url=mock_settings.noaa_api_url)
        result = await client.get_water_temperature("8723214")

    assert result.degraded is True
    assert result.source_status == "cached"
    assert result.value == stale


# ---------------------------------------------------------------------------
# Integration Test 11 — Definition of Done: deliberate-failure mock
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_definition_of_done_deliberate_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """DoD test: mocked-down NOAA source → degraded=True, no unhandled exception.

    This is the concrete Definition-of-Done test from the roadmap §33.
    Asserts:
      - No exception is raised to the caller
      - result.degraded is True
      - source_status is "cached" or "unavailable"
    """
    import respx
    import httpx as _httpx

    fake_redis = _make_redis()
    monkeypatch.setattr("resilience.degraded_mode.get_redis", AsyncMock(return_value=fake_redis))
    monkeypatch.setattr(
        "resilience.circuit_breaker.get_redis", AsyncMock(return_value=fake_redis)
    )

    from config.settings import Settings
    mock_settings = MagicMock(spec=Settings)
    mock_settings.resilience_bypass = False
    mock_settings.circuit_failure_threshold = 5
    mock_settings.circuit_half_open_timeout_s = 60
    mock_settings.noaa_api_url = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
    monkeypatch.setattr("resilience.degraded_mode.get_settings", lambda: mock_settings)
    monkeypatch.setattr("resilience.circuit_breaker.get_settings", lambda: mock_settings)
    monkeypatch.setattr("tools.ocean_noaa.client.get_settings", lambda: mock_settings)

    from tools.ocean_noaa.client import NOAAOceanClient

    import resilience.retry_policy as rp
    from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_none
    no_wait = retry(
        stop=stop_after_attempt(rp.MAX_ATTEMPTS),
        wait=wait_none(),
        retry=retry_if_exception_type(httpx.HTTPError),
        reraise=True,
    )
    monkeypatch.setattr(rp, "_RETRY_POLICY", no_wait)

    # No cache seeded — tests the "unavailable" path
    with respx.mock:
        respx.get(mock_settings.noaa_api_url).mock(
            return_value=_httpx.Response(503, text="Service Unavailable")
        )
        client = NOAAOceanClient(base_url=mock_settings.noaa_api_url)

        # Must not raise
        result = await client.get_water_temperature("8723214")

    assert result.degraded is True, (
        "DoD FAILED: result.degraded must be True when source is down. "
        "Check resilient_call fallback path."
    )
    assert result.source_status in ("cached", "unavailable"), (
        f"DoD FAILED: source_status must be 'cached' or 'unavailable', got '{result.source_status}'"
    )


# ---------------------------------------------------------------------------
# Regression Test 12 — Key builder extensions don't break existing keys
# ---------------------------------------------------------------------------

def test_key_builder_regression() -> None:
    """Existing RedisKeyBuilder methods are unaffected; new methods produce correct namespaces."""
    from cache.keys import RedisKeyBuilder

    # Existing — must be unchanged
    assert RedisKeyBuilder.cache_key("foo") == "gaiaos:cache:foo"
    assert RedisKeyBuilder.checkpoint_key("t1") == "gaiaos:checkpoint:t1"
    assert RedisKeyBuilder.event_channel_key("inv1") == "gaiaos:events:inv1"
    assert RedisKeyBuilder.rate_limit_key("127.0.0.1", "search") == "gaiaos:ratelimit:127.0.0.1:search"
    assert RedisKeyBuilder.station_key(35.68, 139.65, "noaa") == "gaiaos:cache:station:noaa:35.68:139.65"

    # New — circuit and source cache
    assert RedisKeyBuilder.circuit_key("noaa") == "gaiaos:circuit:noaa"
    assert RedisKeyBuilder.circuit_key("usgs") == "gaiaos:circuit:usgs"
    assert RedisKeyBuilder.source_cache_key("noaa", "temp:8723214") == "gaiaos:cache:noaa:temp:8723214"
    assert RedisKeyBuilder.source_cache_key("usgs", "eq:37.5:122.0:100:1.0:7") == (
        "gaiaos:cache:usgs:eq:37.5:122.0:100:1.0:7"
    )
