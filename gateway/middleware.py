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
- No logging framework calls (deferred to Milestone 8).
- No request body inspection.
- No response body modification beyond adding the header.

Auth and rate-limit providers
------------------------------
``GatewayMiddleware.__init__`` accepts ``auth`` and ``rate_limiter`` as
constructor arguments.  The defaults are the Phase 1 stubs.  To activate
real implementations, pass them when registering the middleware in
``app.main.create_app()`` — no other code changes are required.

TODO(M_AUTH):      Pass a real ``AuthProvider`` implementation here once
                   authentication is implemented.
TODO(M_RATELIMIT): Pass a real ``RateLimiter`` implementation here once
                   rate limiting is implemented.
"""

from __future__ import annotations

import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from gateway.auth_stub import AuthProvider, AuthStub
from gateway.context import reset_request_id, set_request_id
from gateway.rate_limit_stub import RateLimiter, RateLimitStub

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
        auth: AuthProvider = AuthStub(),
        rate_limiter: RateLimiter = RateLimitStub(),
    ) -> None:
        super().__init__(app)
        self._auth = auth
        self._rate_limiter = rate_limiter

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        """Process one HTTP request end-to-end.

        Execution order:
            1. Generate request ID.
            2. Set context (request.state + contextvars).
            3. Run auth stub.
            4. Run rate-limit stub.
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
            # --- 3. Auth check (currently a no-op stub) ---
            # TODO(M_AUTH): when auth is enabled, an HTTPException raised here
            # will short-circuit the request before call_next() is reached.
            await self._auth.authenticate(request)

            # --- 4. Rate-limit check (currently a no-op stub) ---
            # TODO(M_RATELIMIT): when rate limiting is enabled, an HTTPException
            # raised here returns 429 before the route handler runs.
            await self._rate_limiter.check(request)

            # --- 5. Continue to the route handler ---
            response: Response = await call_next(request)

        finally:
            # --- 7. Clean up context variable ---
            # Always reset even if auth/rate-limit/handler raised, so the
            # context variable does not leak across requests in tests or when
            # coroutines are recycled.
            reset_request_id(token)

        # --- 6. Inject X-Request-ID into response ---
        # Done after the try/finally block so that the header is always
        # present on successful responses regardless of the inner call order.
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


__all__ = [
    "GatewayMiddleware",
    "REQUEST_ID_HEADER",
]
