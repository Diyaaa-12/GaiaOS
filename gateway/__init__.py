"""Gateway package.

Public surface
--------------
``GatewayMiddleware``
    The single middleware class to add to the FastAPI application.
    Import and register in ``app.main.create_app``.

``get_request_id``
    Read the current request ID from contextvars.  Import from here (or
    directly from ``gateway.context``) in any module that needs it.

``set_request_id`` / ``reset_request_id``
    Context-variable lifecycle helpers.  Intended for use by the middleware
    and for testing; application code should only call ``get_request_id``.

Extension points
----------------
``AuthProvider``   — protocol for future authentication implementations.
``RateLimiter``    — protocol for future rate-limit implementations.
``AuthStub``       — Phase 1 passthrough auth (import from gateway.auth_stub).
``RateLimitStub``  — Phase 1 no-op rate limiter (import from gateway.rate_limit_stub).

Import direction (enforced, no cycles):
    gateway → config          (reads ENABLE_AUTH via settings)
    app     → gateway         (registers middleware, reads request_id)
    gateway ✗→ app            (never)
    gateway ✗→ db             (never)
"""

from gateway.context import get_request_id, reset_request_id, set_request_id
from gateway.middleware import GatewayMiddleware, REQUEST_ID_HEADER

__all__ = [
    "GatewayMiddleware",
    "REQUEST_ID_HEADER",
    "get_request_id",
    "reset_request_id",
    "set_request_id",
]
