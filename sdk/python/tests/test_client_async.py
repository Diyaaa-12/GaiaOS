"""Unit tests for asynchronous AsyncGaiaClient calls."""

import pytest
import respx
from gaiaos_sdk import AsyncGaiaClient
from httpx import Response


@pytest.mark.asyncio
@respx.mock
async def test_investigation_create_async() -> None:
    """AsyncGaiaClient.investigations.create submits query asynchronously."""
    respx.post("http://localhost:8000/api/v1/investigations").mock(
        return_value=Response(
            202,
            json={
                "investigation_id": "87654321-4321-8765-4321-876543218765",
                "status": "accepted",
                "message": "Investigation enqueued successfully.",
                "poll_url": "/api/v1/investigations/87654321-4321-8765-4321-876543218765",
                "stream_url": "/api/v1/investigations/87654321-4321-8765-4321-876543218765/stream",
            },
        )
    )

    async with AsyncGaiaClient(
        base_url="http://localhost:8000", bearer_token="test_token"
    ) as client:
        resp = await client.investigations.create(query="Analyze flood risk in Venice")
        assert str(resp.investigation_id) == "87654321-4321-8765-4321-876543218765"
        assert resp.status == "accepted"
