"""Request-scoped context variables.

This module is the single source of truth for per-request context that must
be accessible without explicit parameter passing.

Design
------
Python's ``contextvars`` module provides coroutine-safe context variables —
each asyncio Task inherits a copy of the context from its creator, so values
set during request processing are not visible in other concurrent requests.

Currently the only context variable is the request ID.  Future milestones may
add variables such as:

- ``_current_user``   — authenticated principal (Milestone auth)
- ``_trace_id``       — distributed trace ID (Milestone observability)
- ``_tenant_id``      — multi-tenancy context

Import direction (no cycles):
    gateway.context → (nothing from this project)
    gateway.middleware → gateway.context
    app.* → gateway.context (read-only, for logging etc.)
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Optional

# ---------------------------------------------------------------------------
# Request ID
# ---------------------------------------------------------------------------

_request_id: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


def set_request_id(value: str) -> Token[Optional[str]]:
    """Store *value* as the request ID for the current request context.

    Returns the ``Token`` produced by ``ContextVar.set()``.  Callers that
    need to reset the variable to its previous value (e.g. in cleanup code)
    should pass this token to :func:`reset_request_id`.
    """
    return _request_id.set(value)


def get_request_id() -> Optional[str]:
    """Return the request ID for the current request context, or ``None``."""
    return _request_id.get()


def reset_request_id(token: Token[Optional[str]]) -> None:
    """Reset the request ID context variable to the value it had before
    the corresponding :func:`set_request_id` call.

    This is called by the middleware's cleanup path to ensure the context
    variable does not leak across requests when coroutines are reused
    (e.g. in test scenarios with a single event loop).
    """
    _request_id.reset(token)


__all__ = [
    "get_request_id",
    "reset_request_id",
    "set_request_id",
]
