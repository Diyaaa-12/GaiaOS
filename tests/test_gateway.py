from __future__ import annotations

import uuid

from httpx import AsyncClient

from gateway.context import get_request_id
from gateway.middleware import REQUEST_ID_HEADER


class TestGatewayMiddleware:
    async def test_request_id_is_generated_when_absent(self, client: AsyncClient) -> None:
        """Verify the middleware generates a new UUID if X-Request-ID is absent."""
        response = await client.get("/api/v1/health/live")
        assert response.status_code == 200

        request_id = response.headers.get(REQUEST_ID_HEADER)
        assert request_id is not None
        # Verify it's a valid UUID
        assert uuid.UUID(request_id).version == 4

    async def test_existing_request_id_is_preserved(self, client: AsyncClient) -> None:
        """Verify the middleware preserves an incoming X-Request-ID."""
        custom_id = "custom-trace-id-12345"
        response = await client.get("/api/v1/health/live", headers={REQUEST_ID_HEADER: custom_id})
        assert response.status_code == 200

        request_id = response.headers.get(REQUEST_ID_HEADER)
        assert request_id == custom_id

    async def test_middleware_cleanup_behaves_correctly(self, client: AsyncClient) -> None:
        """Verify the context variable is cleaned up after the request completes."""
        # Ensure it's clean before
        assert get_request_id() is None

        response = await client.get("/api/v1/health/live")
        assert response.status_code == 200

        # Ensure it's clean after, meaning reset_request_id() worked
        assert get_request_id() is None
