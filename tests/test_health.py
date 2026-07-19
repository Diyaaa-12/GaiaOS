"""Integration tests for health endpoints (Milestone 9).

Tests run against the real FastAPI application with its full lifespan,
including a real PostgreSQL database connection.

Coverage
--------
GET /api/v1/health/live
    - Returns HTTP 200.
    - Body contains ``status == "alive"``.
    - Body contains ``app_version`` (non-empty string).
    - Body contains ``schema_version`` key.

GET /api/v1/health/ready
    - Returns HTTP 200 when the database and extensions are healthy.
    - Body contains ``status == "ready"``.
    - Body contains ``database == "ok"``.
    - Body contains ``schema_version`` key (value may be "unknown" if
      migrations haven't run, but the key must be present).
    - Body contains ``app_version`` (non-empty string).
"""

from __future__ import annotations

from httpx import AsyncClient

from app import __version__


class TestLiveness:
    """Tests for GET /api/v1/health/live."""

    async def test_live_returns_200(self, client: AsyncClient) -> None:
        """Liveness probe always returns HTTP 200."""
        response = await client.get("/api/v1/health/live")
        assert response.status_code == 200

    async def test_live_status_is_alive(self, client: AsyncClient) -> None:
        """Response body contains status == 'alive'."""
        response = await client.get("/api/v1/health/live")
        body = response.json()
        assert body["status"] == "alive"

    async def test_live_app_version_present(self, client: AsyncClient) -> None:
        """Response body contains a non-empty app_version string."""
        response = await client.get("/api/v1/health/live")
        body = response.json()
        assert "app_version" in body
        assert body["app_version"] == __version__
        assert body["app_version"]  # non-empty

    async def test_live_schema_version_present(self, client: AsyncClient) -> None:
        """Response body contains a schema_version key."""
        response = await client.get("/api/v1/health/live")
        body = response.json()
        assert "schema_version" in body

    async def test_live_content_type_is_json(self, client: AsyncClient) -> None:
        """Response Content-Type is application/json."""
        response = await client.get("/api/v1/health/live")
        assert "application/json" in response.headers["content-type"]


class TestReadiness:
    """Tests for GET /api/v1/health/ready.

    These tests require a running PostgreSQL database with PostGIS and
    pgvector installed.  If ``DATABASE_URL`` is not set the ``client``
    fixture skips all tests in this class.
    """

    async def test_ready_returns_200(self, client: AsyncClient) -> None:
        """Readiness probe returns HTTP 200 when all dependencies are healthy."""
        response = await client.get("/api/v1/health/ready")
        assert response.status_code == 200

    async def test_ready_status_is_ready(self, client: AsyncClient) -> None:
        """Response body contains status == 'ready'."""
        response = await client.get("/api/v1/health/ready")
        body = response.json()
        assert body["status"] == "ready"

    async def test_ready_database_is_ok(self, client: AsyncClient) -> None:
        """Response body contains database == 'ok'."""
        response = await client.get("/api/v1/health/ready")
        body = response.json()
        assert body["database"] == "ok"

    async def test_ready_schema_version_present(self, client: AsyncClient) -> None:
        """Response body contains a schema_version key."""
        response = await client.get("/api/v1/health/ready")
        body = response.json()
        assert "schema_version" in body
        # schema_version may be "unknown" if migrations haven't run yet.
        # The important thing is the key exists and is a string.
        assert isinstance(body["schema_version"], str)

    async def test_ready_app_version_present(self, client: AsyncClient) -> None:
        """Response body contains the correct app_version."""
        response = await client.get("/api/v1/health/ready")
        body = response.json()
        assert "app_version" in body
        assert body["app_version"] == __version__

    async def test_ready_content_type_is_json(self, client: AsyncClient) -> None:
        """Response Content-Type is application/json."""
        response = await client.get("/api/v1/health/ready")
        assert "application/json" in response.headers["content-type"]

    async def test_ready_response_has_all_required_fields(self, client: AsyncClient) -> None:
        """Success response contains all fields required by the Milestone 9 schema."""
        response = await client.get("/api/v1/health/ready")
        body = response.json()
        required_fields = {"status", "app_version", "schema_version", "database"}
        assert required_fields.issubset(body.keys())
