"""Redis-backed Token Bucket Rate Limiter.

Implements the ``gateway.rate_limit_stub.RateLimiter`` protocol using an
atomic Redis Lua script.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException, Request

from cache.client import get_redis
from cache.keys import RedisKeyBuilder
from config.settings import get_settings
from logging_config import get_logger

if TYPE_CHECKING:
    from redis.asyncio import Redis

_log = get_logger(__name__)

# Atomic Token Bucket Lua Script
# KEYS[1]: Rate limit key (e.g. gaiaos:ratelimit:<identifier>:<scope>)
# ARGV[1]: max_capacity (burst capacity)
# ARGV[2]: refill_rate_per_sec (tokens per second)
# ARGV[3]: now_timestamp (current epoch time in seconds)
# ARGV[4]: cost (tokens requested)
TOKEN_BUCKET_LUA = """
local key = KEYS[1]
local max_capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local cost = tonumber(ARGV[4])

local data = redis.call("HMGET", key, "tokens", "last_updated")
local tokens = tonumber(data[1])
local last_updated = tonumber(data[2])

if tokens == nil or last_updated == nil then
    tokens = max_capacity
    last_updated = now
else
    local delta = math.max(0, now - last_updated)
    tokens = math.min(max_capacity, tokens + delta * refill_rate)
    last_updated = now
end

local allowed = 0
local retry_after = 0

if tokens >= cost then
    allowed = 1
    tokens = tokens - cost
    redis.call("HMSET", key, "tokens", tokens, "last_updated", last_updated)
    local ttl = math.ceil(max_capacity / refill_rate)
    redis.call("EXPIRE", key, ttl)
else
    allowed = 0
    local needed = cost - tokens
    retry_after = math.ceil(needed / refill_rate)
end

return {allowed, tostring(tokens), tostring(retry_after)}
"""


EXCLUDED_PATH_PREFIXES: tuple[str, ...] = (
    "/health",
    "/api/v1/health",
    "/docs",
    "/openapi.json",
    "/redoc",
)


class RedisRateLimiter:
    """An asynchronous Redis-backed token bucket rate limiter.

    Satisfies the ``gateway.rate_limit_stub.RateLimiter`` protocol.
    Enforces per-principal and per-IP rate limits using atomic Lua scripts.
    Fails open on Redis infrastructure failure to prevent API denial of service.
    """

    def __init__(self, client: Redis | None = None) -> None:
        self._client = client
        self._script_sha: str | None = None

    async def _get_redis(self) -> Redis:
        if self._client is not None:
            return self._client
        return await get_redis()

    def _extract_identity_and_role(self, request: Request) -> tuple[str, str]:
        """Extract caller identifier and role from request state or client IP."""
        user = getattr(request.state, "user", None)
        if user is not None and getattr(user, "id", None):
            role_val = getattr(user.role, "value", str(user.role))
            return f"user:{user.id}", role_val

        # Fallback to client IP for unauthenticated requests
        x_forwarded_for = request.headers.get("X-Forwarded-For")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0].strip()
        elif request.client and request.client.host:
            ip = request.client.host
        else:
            ip = "unknown"

        return f"ip:{ip}", "public"

    def _resolve_scope(self, request: Request) -> str:
        """Resolve rate limiting scope/action based on URL path."""
        path = request.url.path
        if path.startswith("/api/v1/investigations"):
            return "submit_investigation" if request.method == "POST" else "investigations"
        if path.startswith("/api/v1/auth"):
            return "auth"
        return "api"

    def _get_quota_for_role(self, role: str) -> tuple[int, int]:
        """Return (requests_per_minute, burst) tuple based on caller role."""
        settings = get_settings()
        base_rpm = settings.rate_limit_requests_per_minute
        base_burst = settings.rate_limit_burst

        role_lower = str(role).lower()
        if role_lower == "admin":
            return base_rpm * 10, base_burst * 5
        elif role_lower == "researcher":
            return base_rpm * 3, base_burst * 2
        elif role_lower in ("user", "authenticated"):
            return base_rpm, base_burst
        else:
            # Public / Unauthenticated quota
            return min(base_rpm, 10), min(base_burst, 5)

    async def check(self, request: Request) -> None:
        """Enforce rate limits for the given request.

        Raises:
            fastapi.HTTPException: 429 Too Many Requests if caller exceeded limit.
        """
        path = request.url.path
        if path == "/" or any(
            path == prefix or path.startswith(prefix + "/") for prefix in EXCLUDED_PATH_PREFIXES
        ):
            return

        settings = get_settings()
        if not settings.enable_rate_limiting:
            return

        identifier, role = self._extract_identity_and_role(request)
        scope = self._resolve_scope(request)
        requests_per_minute, burst = self._get_quota_for_role(role)

        key = RedisKeyBuilder.rate_limit_key(identifier, scope)
        refill_rate = requests_per_minute / 60.0
        capacity = max(1, burst)
        now = time.time()
        cost = 1

        try:
            client = await self._get_redis()
            if self._script_sha is None:
                self._script_sha = await client.script_load(TOKEN_BUCKET_LUA)

            try:
                eval_coro: Any = client.evalsha(
                    self._script_sha,
                    1,
                    key,
                    str(capacity),
                    str(refill_rate),
                    str(now),
                    str(cost),
                )
                res: Any = await eval_coro
            except Exception:
                # Script SHA might be flushed; fallback to EVAL
                eval_fallback_coro: Any = client.eval(
                    TOKEN_BUCKET_LUA,
                    1,
                    key,
                    str(capacity),
                    str(refill_rate),
                    str(now),
                    str(cost),
                )
                res = await eval_fallback_coro

            allowed = int(res[0])
            retry_after = int(res[2]) if len(res) > 2 else 1

            if allowed == 0:
                _log.info(
                    "gateway.ratelimit.exceeded",
                    identifier=identifier,
                    scope=scope,
                    role=role,
                    retry_after=retry_after,
                )
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded. Please try again later.",
                    headers={"Retry-After": str(max(1, retry_after))},
                )

        except HTTPException:
            raise
        except Exception as exc:
            # Fail-open behavior: log infrastructure exception and permit request
            _log.warning(
                "gateway.ratelimit.fail_open",
                identifier=identifier,
                scope=scope,
                error=str(exc),
            )
            return


__all__ = ["RedisRateLimiter", "TOKEN_BUCKET_LUA"]
