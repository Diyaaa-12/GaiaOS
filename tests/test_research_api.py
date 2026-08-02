"""Integration tests for Public Research API endpoints — Phase 5 Milestone 9."""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_redis_dependency
from config.settings import get_settings
from db.repository import InvestigationRepository


@pytest.mark.asyncio
class TestPublicResearchAPI:
    """Test suite for /api/v1/research/* endpoints."""

    @pytest.fixture(autouse=True)
    def override_redis_dep(self, app: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        """Override Redis dependency to provide a mock client and prevent connection errors."""
        monkeypatch.setenv("USE_QUEUED_EXECUTION", "false")
        get_settings.cache_clear()

        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)

        async def _mock_get_redis() -> Any:
            yield mock_redis

        app.dependency_overrides[get_redis_dependency] = _mock_get_redis

    async def test_create_investigation_with_consent(
        self, db_session: AsyncSession, client: AsyncClient
    ) -> None:
        """Creating an investigation with consent_public_research=True persists flag in DB."""
        payload = {
            "query": "What are the recent seismic activity trends near San Andreas?",
            "consent_public_research": True,
        }
        res = await client.post("/api/v1/investigations", json=payload)
        assert res.status_code == 202
        data = res.json()
        inv_id = uuid.UUID(data["investigation_id"])

        inv = await InvestigationRepository.get_investigation(db_session, inv_id)
        assert inv is not None
        assert inv.consent_public_research is True

    async def test_list_public_research_investigations_filtering(
        self, db_session: AsyncSession, client: AsyncClient
    ) -> None:
        """List public research investigations applies anonymization policy."""
        # Insert completed investigation
        inv = await InvestigationRepository.create_investigation(
            session=db_session,
            query="Japanese seismic fault line analysis",
            consent_public_research=False,
        )
        await InvestigationRepository.update_investigation_status(
            session=db_session,
            investigation_id=inv.id,
            status="complete",
            complexity_tier="complex",
            answer="Fault line analysis complete.",
            confidence=0.95,
            execution_trace={"domains": ["seismic"]},
        )

        res = await client.get("/api/v1/research/investigations")
        assert res.status_code == 200
        items = res.json()
        assert len(items) >= 1

        match = next((i for i in items if i["investigation_id"] == str(inv.id)), None)
        assert match is not None
        assert match["consent_public_research"] is False
        assert match["query_text"] is None
        assert match["query_category"] == "seismic_research"

    async def test_public_research_api_disabled_by_feature_flag(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When public_research_api_enabled is False, research endpoints return 503."""
        monkeypatch.setenv("PUBLIC_RESEARCH_API_ENABLED", "false")
        get_settings.cache_clear()

        try:
            res = await client.get("/api/v1/research/investigations")
            assert res.status_code == 503
            assert res.json()["error_code"] == "public_research_api_disabled"
        finally:
            get_settings.cache_clear()

    async def test_list_public_hazard_events(
        self, db_session: AsyncSession, client: AsyncClient
    ) -> None:
        """Hazard events endpoint returns public hazard data."""
        # Seed test hazard event
        event_id = uuid.uuid4()
        await db_session.execute(
            text("""
                INSERT INTO hazard_events
                (id, event_type, region_label, event_date, details, source, external_id, created_at)
                VALUES
                (:id, 'earthquake', 'Tokyo Region', now(), 'Magnitude 5.8', 'USGS', :ext, now())
                ON CONFLICT DO NOTHING
            """),
            {"id": event_id, "ext": f"usgs_{event_id}"},
        )
        await db_session.commit()

        res = await client.get("/api/v1/research/hazard-events?event_type=earthquake")
        assert res.status_code == 200
        events = res.json()
        assert len(events) >= 1
        assert any(e["id"] == str(event_id) for e in events)
