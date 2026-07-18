"""Rate-limit stub — interface and no-op implementation for Phase 1.

This module defines the contract that real rate limiting will fulfil in a
later milestone.  The concrete implementation (``RateLimitStub``) always
permits requests, making it a true no-op until a real backend (Redis,
token bucket, etc.) is wired in.

Replacing rate limiting
------------------------
When a real rate-limit backend is ready:

1.  Create a new class that satisfies the ``RateLimiter`` protocol.
2.  Swap the class used in ``gateway.middleware.GatewayMiddleware`` (a
    single constructor argument).
3.  No route definitions and no existing middleware logic need to change.

Suggested future implementations:

- Redis token bucket (sliding window per principal + per IP)
- In-process leaky bucket (useful for tests and single-instance staging)
- Passthrough (this stub) for dev environments

TODO(M_RATELIMIT): Implement a Redis-backed token-bucket rate limiter.
                   Store limits in Settings as RATE_LIMIT_REQUESTS_PER_MINUTE
                   and RATE_LIMIT_BURST.  Return 429 Too Many Requests with
                   Retry-After when the limit is exceeded.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from fastapi import Request


# ---------------------------------------------------------------------------
# Protocol — the interface that all rate-limit implementations must satisfy
# ---------------------------------------------------------------------------

@runtime_checkable
class RateLimiter(Protocol):
    """Interface for rate-limiting providers.

    Any object that implements ``check`` satisfies this protocol.
    Future implementations (Redis, in-process, etc.) plug in here without
    changing the middleware.

    ``check`` must be a coroutine so that implementations can perform async
    I/O (e.g. INCR/EXPIRE against Redis).
    """

    async def check(self, request: Request) -> None:
        """Enforce the rate limit for the given request.

        Raises:
            fastapi.HTTPException: 429 Too Many Requests if the caller has
                exceeded its allowed rate.  The response should include a
                ``Retry-After`` header indicating when the client may retry.

        Returns:
            None if the request is within the allowed rate.

        TODO(M_RATELIMIT): Decide the rate-limit key strategy:
                           - by IP address (``request.client.host``)
                           - by authenticated principal (``request.state.user``)
                           - by API key
                           - a combination of the above
        """
        ...  # pragma: no cover


# ---------------------------------------------------------------------------
# Stub implementation — Phase 1 no-op
# ---------------------------------------------------------------------------

class RateLimitStub:
    """Passthrough rate-limit stub for Phase 1.

    Always permits the request.  No counters, no storage, no I/O.

    Satisfies the ``RateLimiter`` protocol so it is a valid drop-in for
    the real implementation.

    TODO(M_RATELIMIT): Replace this class with a real rate limiter once
                       Redis is available (Milestone Redis/cache layer).
    """

    async def check(self, request: Request) -> None:
        """Permit the request unconditionally.

        This is intentionally a no-op.  It must not count requests, must
        not read from any store, and must not modify ``request.state``.

        TODO(M_RATELIMIT): Replace this body with rate-limit enforcement logic.
        """
        # STUB: rate limiting is disabled.  All requests are permitted.
        return


__all__ = [
    "RateLimiter",
    "RateLimitStub",
]
