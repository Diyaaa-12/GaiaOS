"""Process-lifetime shared HTTP client factory for tool clients."""

from __future__ import annotations

import asyncio

import httpx

from logging_config import get_logger

_log = get_logger(__name__)

_shared_client: httpx.AsyncClient | None = None
_client_loop: asyncio.AbstractEventLoop | None = None


async def get_shared_client() -> httpx.AsyncClient:
    """Return the shared httpx.AsyncClient instance bound to the running event loop.

    Lazily initializes a single client instance reused across all tool clients
    under tools/ for connection pooling. Automatically recreates the client
    if the running event loop changes (e.g. between RQ jobs).
    """
    global _shared_client, _client_loop
    current_loop = asyncio.get_running_loop()

    if _shared_client is not None and (
        _shared_client.is_closed or _client_loop is not current_loop
    ):
        await close_shared_client()

    if _shared_client is None:
        _log.info("http_client.init_shared")
        _shared_client = httpx.AsyncClient(timeout=10.0, follow_redirects=True)
        _client_loop = current_loop

    return _shared_client


async def close_shared_client() -> None:
    """Close the shared HTTP client and release resources.

    Idempotent: safe to call multiple times during shutdown.
    """
    global _shared_client, _client_loop
    if _shared_client is not None:
        client = _shared_client
        _shared_client = None
        _client_loop = None
        if not client.is_closed:
            _log.info("http_client.close_shared")
            try:
                await client.aclose()
            except Exception as exc:
                _log.warning("http_client.close_warning", error=str(exc))
