"""Gateway middleware — request interception layer.

Every HTTP request handled by the GaiaOS FastAPI application passes through
``GatewayMiddleware`` before reaching any route handler.

Responsibilities (and ONLY these):
1. Generate a unique request ID.
2. Store it on ``request.state.request_id`` and in ``gateway.context``
   (contextvars) so it is accessible without explicit parameter passing.
3. Run the auth stub (currently a no-op; future: real AuthN enforcement).
4. Run the rate-limit stub (currently a no-op; future: Redis token bucket).
5. Call the next middleware / route handler.
6. Inject ``X-Request-ID`` into the response headers.
7. Clean up the context variable regardless of success or failure.

What the middleware intentionally does NOT do:
- No business logic.
- No database access.
- No orchestration.
- No request body inspection (security: bodies are never logged by default).
- No response body modification beyond adding the header.
- No Authorization headers, passwords, or tokens are ever logged.

Request logging
---------------
One structured access-log entry is emitted per request with:
  method, path, status_code, duration_ms, request_id

The ``request_id`` is read from contextvars (set earlier in ``dispatch``),
not regenerated, so it matches the value in the response header.

To add request-body logging in a future milestone, add a processor or a
conditional hook here (e.g. ``if settings.log_request_body``) with
appropriate redaction — never log raw bodies unconditionally.

Auth and rate-limit providers
------------------------------
``GatewayMiddleware.__init__`` accepts ``auth`` and ``rate_limiter`` as
constructor arguments.  If omitted (or passed as ``None``), they default
to the Phase 1 stubs internally.  To activate real implementations, pass
them when registering the middleware in ``app.main.create_app()`` — no
other code changes are required.

TODO(M_AUTH):      Pass a real ``AuthProvider`` implementation here once
                   authentication is implemented.
TODO(M_RATELIMIT): Pass a real ``RateLimiter`` implementation here once
                   rate limiting is implemented.
"""

from __future__ import annotations

import time
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from gateway.auth_stub import AuthProvider, AuthStub
from gateway.context import reset_request_id, set_request_id
from gateway.rate_limit_stub import RateLimiter, RateLimitStub
from logging_config import get_logger

_log = get_logger(__name__)

# The HTTP response header that carries the request ID.
REQUEST_ID_HEADER: str = "X-Request-ID"


class GatewayMiddleware(BaseHTTPMiddleware):
    """Thin request-context middleware that gates every incoming request.

    Registration (in ``app.main.create_app``):

        app.add_middleware(GatewayMiddleware)

    FastAPI / Starlette add middleware in reverse order, so the LAST
    ``add_middleware`` call wraps the outermost layer.  Register this
    middleware AFTER all other middleware so it runs FIRST on every request.

    Swapping providers (future milestones):

        app.add_middleware(
            GatewayMiddleware,
            auth=MyRealAuthProvider(),
            rate_limiter=MyRedisRateLimiter(),
        )
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        auth: AuthProvider | list[AuthProvider] | None = None,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        super().__init__(app)
        if auth is None:
            self._auth_chain: list[AuthProvider] = [AuthStub()]
        elif isinstance(auth, list):
            self._auth_chain = auth
        else:
            self._auth_chain = [auth]
        self._rate_limiter = rate_limiter if rate_limiter is not None else RateLimitStub()

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        """Process one HTTP request end-to-end.

        Execution order:
            1. Generate request ID.
            2. Set context (request.state + contextvars).
            3. Run auth chain (e.g. ApiKeyAuthProvider then JWTAuthProvider).
            4. Run rate-limit check.
            5. Call the next layer (route handler or inner middleware).
            6. Attach X-Request-ID to the response.
            7. Reset context variable (cleanup, always runs).
        """
        # --- 1. Generate request ID ---
        # Honour an upstream X-Request-ID if present (e.g. from a load balancer
        # or an API management proxy).  Generate a fresh UUID4 otherwise.
        request_id: str = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())

        # --- 2. Attach to request.state and to contextvars ---
        request.state.request_id = request_id
        token = set_request_id(request_id)

        try:
            # --- 3. Auth check (chained) ---
            # If X-API-Key header is present, ApiKeyAuthProvider executes first.
            # If user or api_key_error is attached, execution short-circuits.
            # Otherwise, falls through to JWTAuthProvider.
            for provider in self._auth_chain:
                await provider.authenticate(request)
                if (
                    getattr(request.state, "user", None) is not None
                    or getattr(request.state, "api_key_error", None) is not None
                ):
                    break

            # --- 4. Rate-limit check ---
            await self._rate_limiter.check(request)

            # --- 5. Continue to the route handler ---
            start_ms: float = time.monotonic() * 1_000
            response: Response = await call_next(request)
            duration_ms: float = round(time.monotonic() * 1_000 - start_ms, 2)

        finally:
            # --- 7. Clean up context variable ---
            reset_request_id(token)

        # --- 6. Inject X-Request-ID into response ---
        response.headers[REQUEST_ID_HEADER] = request_id

        # --- 8. Emit structured access log ---
        # Security: only safe, non-sensitive fields are logged.
        # Authorization headers, raw API keys, and tokens are NEVER logged.
        log_kwargs = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        }
        api_key_id = getattr(request.state, "api_key_id", None)
        if api_key_id is not None:
            log_kwargs["key_id"] = api_key_id

        _log.info("request", **log_kwargs)

        return response


__all__ = [
    "GatewayMiddleware",
    "REQUEST_ID_HEADER",
]
