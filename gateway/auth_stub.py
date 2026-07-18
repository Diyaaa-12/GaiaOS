"""Auth stub — interface and no-op implementation for Phase 1.

This module defines the contract that real authentication will fulfil in a
later milestone.  The concrete implementation (``AuthStub``) allows every
request through, making it safe to deploy in development without any IdP
configuration.

Replacing authentication
-------------------------
When a real auth provider is ready:

1.  Create a new class that satisfies the ``AuthProvider`` protocol.
2.  Swap the class used in ``gateway.middleware.GatewayMiddleware`` (a
    single constructor argument).
3.  Set ``ENABLE_AUTH=true`` in the environment to activate enforcement.
4.  Delete this stub or retain it as the dev/test bypass.

No route definitions, no dependency-injection wiring, and no existing
middleware logic need to change.

TODO(M_AUTH): Replace AuthStub with a real implementation that validates
              bearer tokens against the configured identity provider.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from fastapi import Request


# ---------------------------------------------------------------------------
# Protocol — the interface that all auth implementations must satisfy
# ---------------------------------------------------------------------------

@runtime_checkable
class AuthProvider(Protocol):
    """Interface for authentication providers.

    Any object that implements ``authenticate`` satisfies this protocol.
    Future implementations (JWT, API-key, mTLS) plug in here without
    changing the middleware.

    ``authenticate`` must be a coroutine so that future implementations can
    perform async I/O (e.g. token introspection, JWKS fetch).
    """

    async def authenticate(self, request: Request) -> None:
        """Validate the request credentials.

        Raises:
            fastapi.HTTPException: 401 if credentials are missing or invalid,
                403 if the principal lacks the required scope.

        Returns:
            None on success.  The implementation may also attach a principal
            object to ``request.state`` (e.g. ``request.state.user``).

        TODO(M_AUTH): Document the exact credential format expected (Bearer
                      token in Authorization header, API key in X-API-Key, etc.)
                      once the auth provider is decided.
        """
        ...  # pragma: no cover


# ---------------------------------------------------------------------------
# Stub implementation — Phase 1 no-op
# ---------------------------------------------------------------------------

class AuthStub:
    """Passthrough authentication stub for Phase 1.

    Allows every request unconditionally.  Activated when ``ENABLE_AUTH``
    is ``false`` (the default) or when ``GAIAOS_ENV`` is ``"dev"``.

    Satisfies the ``AuthProvider`` protocol so it is a valid drop-in for
    the real implementation.

    TODO(M_AUTH): Remove or retain this class as a dev-bypass once real auth
                  is implemented.  In production, this class must never be
                  active unless ENABLE_AUTH is explicitly set to false via
                  an environment variable that is guarded by an ops policy.
    """

    async def authenticate(self, request: Request) -> None:
        """Allow the request without any credential check.

        This is intentionally a no-op.  It is the *only* correct behaviour
        for a stub: it does not log, does not modify the request, and does
        not return any principal information.

        TODO(M_AUTH): Replace this body with credential validation logic.
        """
        # STUB: auth is disabled.  All requests are permitted.
        return


__all__ = [
    "AuthProvider",
    "AuthStub",
]
