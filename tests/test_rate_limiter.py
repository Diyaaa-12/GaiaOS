"""Unit and integration tests for RedisRateLimiter and rate limiting middleware."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, Request

from auth.roles import Role
from config.settings import get_settings
from gateway.rate_limiter_redis import RedisRateLimiter


class DummyUser:
    def __init__(self, user_id: uuid.UUID, role: Role) -> None:
        self.id = user_id
        self.role = role


@pytest.fixture
def mock_request() -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/investigations",
        "headers": [],
        "client": ("192.168.1.100", 54321),
    }
    req = Request(scope)
    req.state.user = None
    return req


class TestRedisRateLimiterUnit:
    """Unit tests for identity extraction, role quota resolution, and fail-open behavior."""

    def test_extract_identity_unauthenticated_client_host(self, mock_request: Request) -> None:
        limiter = RedisRateLimiter()
        identifier, role = limiter._extract_identity_and_role(mock_request)
        assert identifier == "ip:192.168.1.100"
        assert role == "public"

    def test_extract_identity_x_forwarded_for(self) -> None:
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/health",
            "headers": [(b"x-forwarded-for", b"203.0.113.195, 70.41.3.18")],
            "client": ("10.0.0.1", 12345),
        }
        req = Request(scope)
        req.state.user = None

        limiter = RedisRateLimiter()
        identifier, role = limiter._extract_identity_and_role(req)
        assert identifier == "ip:203.0.113.195"
        assert role == "public"

    def test_extract_identity_authenticated_user(self, mock_request: Request) -> None:
        u_id = uuid.uuid4()
        mock_request.state.user = DummyUser(u_id, Role.RESEARCHER)

        limiter = RedisRateLimiter()
        identifier, role = limiter._extract_identity_and_role(mock_request)
        assert identifier == f"user:{u_id}"
        assert role == "researcher"

    def test_resolve_scope(self, mock_request: Request) -> None:
        limiter = RedisRateLimiter()
        assert limiter._resolve_scope(mock_request) == "submit_investigation"

        get_req = Request(
            {"type": "http", "method": "GET", "path": "/api/v1/investigations/123", "headers": []}
        )
        assert limiter._resolve_scope(get_req) == "investigations"

        auth_req = Request(
            {"type": "http", "method": "POST", "path": "/api/v1/auth/login", "headers": []}
        )
        assert limiter._resolve_scope(auth_req) == "auth"

    def test_get_quota_for_role(self) -> None:
        limiter = RedisRateLimiter()
        rpm_admin, burst_admin = limiter._get_quota_for_role("admin")
        rpm_pub, burst_pub = limiter._get_quota_for_role("public")

        assert rpm_admin > rpm_pub
        assert burst_admin > burst_pub
        assert rpm_pub == 10
        assert burst_pub == 5

    @pytest.mark.asyncio
    async def test_check_bypassed_when_disabled(
        self, mock_request: Request, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ENABLE_RATE_LIMITING", "false")
        get_settings.cache_clear()

        limiter = RedisRateLimiter()
        # Should return cleanly without touching Redis
        await limiter.check(mock_request)

        get_settings.cache_clear()

    @pytest.mark.asyncio
    async def test_check_fail_open_on_redis_error(
        self, mock_request: Request, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ENABLE_RATE_LIMITING", "true")
        get_settings.cache_clear()

        mock_client = AsyncMock()
        mock_client.script_load.side_effect = Exception("Redis connection refused")

        limiter = RedisRateLimiter(client=mock_client)
        # Fail-open: should log warning and return cleanly without raising HTTPException
        await limiter.check(mock_request)

        get_settings.cache_clear()

    @pytest.mark.asyncio
    async def test_check_raises_429_when_exceeded(
        self, mock_request: Request, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ENABLE_RATE_LIMITING", "true")
        get_settings.cache_clear()

        mock_client = AsyncMock()
        mock_client.script_load.return_value = "sha_hash_123"
        # Script returns: [allowed=0, remaining_tokens="0", retry_after="5"]
        mock_client.evalsha.return_value = [0, "0", "5"]

        limiter = RedisRateLimiter(client=mock_client)

        with pytest.raises(HTTPException) as exc_info:
            await limiter.check(mock_request)

        assert exc_info.value.status_code == 429
        assert "Rate limit exceeded" in exc_info.value.detail
        assert exc_info.value.headers is not None
        assert exc_info.value.headers.get("Retry-After") == "5"

        get_settings.cache_clear()

    @pytest.mark.asyncio
    async def test_check_allows_when_permitted(
        self, mock_request: Request, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ENABLE_RATE_LIMITING", "true")
        get_settings.cache_clear()

        mock_client = AsyncMock()
        mock_client.script_load.return_value = "sha_hash_123"
        # Script returns: [allowed=1, remaining_tokens="14", retry_after="0"]
        mock_client.evalsha.return_value = [1, "14", "0"]

        limiter = RedisRateLimiter(client=mock_client)
        await limiter.check(mock_request)

        get_settings.cache_clear()

    @pytest.mark.asyncio
    async def test_check_bypassed_for_excluded_health_paths(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ENABLE_RATE_LIMITING", "true")
        get_settings.cache_clear()

        mock_client = AsyncMock()
        # If health paths were not excluded, evalsha would be called
        mock_client.script_load.side_effect = Exception("Should not be called for health routes")

        limiter = RedisRateLimiter(client=mock_client)
        excluded_paths = (
            "/health/live",
            "/health/ready",
            "/api/v1/health/live",
            "/docs",
            "/openapi.json",
        )
        for path in excluded_paths:
            req = Request({"type": "http", "method": "GET", "path": path, "headers": []})
            await limiter.check(req)

        get_settings.cache_clear()
