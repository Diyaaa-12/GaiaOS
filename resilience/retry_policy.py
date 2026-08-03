"""Shared retry policy for GaiaOS external tool calls (Phase 6 Milestone 1).

Provides a single, consistent ``tenacity`` retry configuration reused by
``resilient_call`` in ``resilience.degraded_mode``.  All external HTTP calls
go through this policy — never inline ad-hoc retry logic in individual clients.

Policy:
  - Max 3 attempts (1 initial + 2 retries).
  - Exponential backoff with full jitter: wait = random(0, min(cap, base * 2^n)).
  - Retries on ``httpx.HTTPError`` (covers status errors, network errors, timeouts).
  - Does NOT retry on non-retriable exceptions (e.g. ``ValueError``, ``TypeError``).
"""

from __future__ import annotations

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

# ---------------------------------------------------------------------------
# Public constant — used in tests to verify the attempt ceiling
# ---------------------------------------------------------------------------
MAX_ATTEMPTS: int = 3

# ---------------------------------------------------------------------------
# Shared retry decorator
# ---------------------------------------------------------------------------
_RETRY_POLICY = retry(
    stop=stop_after_attempt(MAX_ATTEMPTS),
    wait=wait_random_exponential(multiplier=0.5, max=10),
    retry=retry_if_exception_type(httpx.HTTPError),
    reraise=True,  # raise the original exception after exhaustion
)


def with_retry(fn):  # type: ignore[no-untyped-def]
    """Wrap an async callable with the shared retry policy.

    Intended for use inside ``resilient_call`` only — do not apply directly
    to tool-client methods, which route through ``resilient_call``.

    Args:
        fn: An async callable (zero-argument lambda) to wrap.

    Returns:
        A tenacity-wrapped version of ``fn``.
    """
    return _RETRY_POLICY(fn)
