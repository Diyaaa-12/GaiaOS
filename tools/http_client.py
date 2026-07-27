"""Process-lifetime shared HTTP client factory for tool clients."""

from __future__ import annotations

import asyncio

import httpx

from logging_config import get_logger

_log = get_logger(__name__)

_shared_client: httpx.AsyncClient | None = None
_client_lock = asyncio.Lock()


async def get_shared_client() -> httpx.AsyncClient:
    """Return the process-lifetime shared httpx.AsyncClient instance.

    Lazily initializes a single client instance reused across all tool clients
    under tools/ for connection pooling and reduced latency. Uses double-checked
    locking with asyncio.Lock for concurrency safety.
    """
    global _shared_client
    if _shared_client is None or _shared_client.is_closed:
        async with _client_lock:
            if _shared_client is None or _shared_client.is_closed:
                _log.info("http_client.init_shared")
                _shared_client = httpx.AsyncClient(timeout=10.0, follow_redirects=True)
    return _shared_client


async def close_shared_client() -> None:
    """Close the shared HTTP client and release resources.

    Idempotent: safe to call multiple times during shutdown.
    """
    global _shared_client
    if _shared_client is not None:
        async with _client_lock:
            if _shared_client is not None:
                client = _shared_client
                _shared_client = None
                if not client.is_closed:
                    _log.info("http_client.close_shared")
                    try:
                        await client.aclose()
                    except Exception as exc:
                        _log.warning("http_client.close_warning", error=str(exc))
