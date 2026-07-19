"""Integration tests for user investigations API endpoints."""

from __future__ import annotations

import asyncio
import uuid

import pytest
import respx
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.investigation import Investigation


class TestInvestigationsAPI:
    """Verifies creation, polling, and failure paths of the investigations API."""

    @respx.mock
    async def test_investigation_e2e_flow(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        # Mock OpenAQ API response
        respx.get("https://api.openaq.org/v2/latest").respond(
            json={
                "results": [
                    {
                        "location": "Paris-North",
                        "measurements": [
                            {"parameter": "pm25", "value": 15.0, "unit": "ug/m3"},
                        ],
                    }
                ]
            },
            status_code=200,
        )

        # 1. Post new investigation
        payload = {"query": "What is the air quality in Paris?"}
        response = await client.post("/api/v1/investigations", json=payload)
        assert response.status_code == 202

        body = response.json()
        assert body["status"] == "accepted"
        assert "investigation_id" in body

        investigation_id = uuid.UUID(body["investigation_id"])
        poll_url = body["poll_url"]
        assert poll_url == f"/api/v1/investigations/{investigation_id}"

        # 2. Wait and poll until status is 'complete'
        max_attempts = 10
        completed = False
        for _ in range(max_attempts):
            await asyncio.sleep(0.5)
            poll_resp = await client.get(poll_url)
            assert poll_resp.status_code == 200
            poll_body = poll_resp.json()
            if poll_body["status"] == "complete":
                completed = True
                assert "Paris-North" in poll_body["answer"]
                assert poll_body["complexity_tier"] == "trivial"
                assert poll_body["execution_trace"]["evidence_count"] == 1
                break

        assert completed is True

        # 3. Verify database row persistence
        stmt = select(Investigation).where(Investigation.id == investigation_id)
        db_row = (await db_session.execute(stmt)).scalar_one()
        assert db_row.status == "complete"
        assert db_row.complexity_tier == "trivial"
        assert "Paris-North" in db_row.answer

    @respx.mock
    async def test_investigation_complex_e2e_flow(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        # Mock OpenAQ API response
        respx.get("https://api.openaq.org/v2/latest").respond(
            json={
                "results": [
                    {
                        "location": "Paris-South",
                        "measurements": [
                            {"parameter": "pm10", "value": 30.0, "unit": "ug/m3"},
                        ],
                    }
                ]
            },
            status_code=200,
        )

        # 1. Post new complex investigation
        payload = {"query": "Predict plume dispersion and current air quality in Paris"}
        response = await client.post("/api/v1/investigations", json=payload)
        assert response.status_code == 202

        body = response.json()
        assert body["status"] == "accepted"
        investigation_id = uuid.UUID(body["investigation_id"])
        poll_url = body["poll_url"]

        # 2. Wait and poll until status is 'complete'
        max_attempts = 10
        completed = False
        for _ in range(max_attempts):
            await asyncio.sleep(0.5)
            poll_resp = await client.get(poll_url)
            assert poll_resp.status_code == 200
            poll_body = poll_resp.json()
            if poll_body["status"] == "complete":
                completed = True
                assert "Paris-South" in poll_body["answer"]
                assert poll_body["complexity_tier"] == "complex"
                assert "fan_out" in poll_body["execution_trace"]["nodes_executed"]
                break

        assert completed is True

        # 3. Verify database row persistence
        stmt = select(Investigation).where(Investigation.id == investigation_id)
        db_row = (await db_session.execute(stmt)).scalar_one()
        assert db_row.status == "complete"
        assert db_row.complexity_tier == "complex"
        assert "fan_out" in db_row.execution_trace["nodes_executed"]

    async def test_get_investigation_not_found(self, client: AsyncClient) -> None:
        bad_id = uuid.uuid4()
        response = await client.get(f"/api/v1/investigations/{bad_id}")
        assert response.status_code == 404
        assert response.json()["error_code"] == "investigation_not_found"

    async def test_post_investigation_validation_error(self, client: AsyncClient) -> None:
        # Query too short
        payload = {"query": "ab"}
        response = await client.post("/api/v1/investigations", json=payload)
        assert response.status_code == 422

    async def test_post_investigation_checkpointer_unavailable(
        self,
        client: AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Mock ping to raise Exception
        async def mock_ping(*args, **kwargs) -> bool:
            raise Exception("Redis timeout")

        monkeypatch.setattr(Redis, "ping", mock_ping)

        payload = {"query": "What is the air quality in Beijing?"}
        response = await client.post("/api/v1/investigations", json=payload)

        assert response.status_code == 503
        body = response.json()
        assert body["error_code"] == "checkpointer_unavailable"
