"""Tests for process-lifetime shared HTTP client lifecycle."""

from __future__ import annotations

import pytest

from tools.http_client import close_shared_client, get_shared_client


@pytest.mark.asyncio
async def test_shared_client_singleton_reuse() -> None:
    """Verify get_shared_client returns the exact same singleton instance on repeated calls."""
    client1 = await get_shared_client()
    client2 = await get_shared_client()

    assert client1 is client2
    assert not client1.is_closed

    await close_shared_client()


@pytest.mark.asyncio
async def test_shared_client_close_and_reinit() -> None:
    """Verify close_shared_client closes instance and subsequent call creates a new instance."""
    client1 = await get_shared_client()
    await close_shared_client()

    assert client1.is_closed

    client2 = await get_shared_client()
    assert client2 is not client1
    assert not client2.is_closed

    await close_shared_client()


@pytest.mark.asyncio
async def test_shared_client_close_idempotent() -> None:
    """Verify close_shared_client can be called repeatedly without error (idempotent shutdown)."""
    await get_shared_client()

    await close_shared_client()
    await close_shared_client()  # Repeated call must not raise
    await close_shared_client()
