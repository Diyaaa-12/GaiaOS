"""Resilience layer for GaiaOS external tool calls (Phase 6 Milestone 1).

Public surface:
- ``resilient_call(source, fn, cache_key, ttl)``: main entry point
- ``ResilientResult``: typed result container
- ``TTL_BY_SOURCE``: per-source cache TTL table

Dependency direction: ``resilience/ → cache/, config/``
Imported by: every ``tools/*`` client.
"""

from resilience.degraded_mode import ResilientResult, TTL_BY_SOURCE, resilient_call

__all__ = [
    "resilient_call",
    "ResilientResult",
    "TTL_BY_SOURCE",
]
