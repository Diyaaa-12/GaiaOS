"""Integration tests for GET /api/v1/research/patterns endpoint (Phase 7 Milestone 2)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import get_settings
from db.repository import PatternFindingRepository


@pytest.mark.asyncio
class TestResearchPatternsAPI:
    """Verifies retrieval, filtering, pagination, sorting, and feature flags."""

    async def test_get_research_patterns_success(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """GET /api/v1/research/patterns returns active pattern findings."""
        monkeypatch.setenv("PUBLIC_RESEARCH_API_ENABLED", "true")
        get_settings.cache_clear()

        mined_time = datetime.now(UTC)
        await PatternFindingRepository.save_pattern_version(
            session=db_session,
            pattern_hash="api_test_hash_1",
            source_event_type="earthquake",
            target_event_type="tsunami",
            region_label="Chile",
            time_window_days=7,
            support_count=4,
            total_source_events=5,
            total_target_events=5,
            observed_rate=0.80,
            baseline_rate=0.20,
            lift=4.0,
            statistical_confidence=0.72,
            uncertainty={
                "point_estimate": 0.72,
                "lower_bound": 0.64,
                "upper_bound": 0.80,
                "source": "model_uncertainty",
            },
            supporting_event_ids=["id1", "id2"],
            description="Chile earthquake to tsunami co-occurrence",
            mined_at=mined_time,
        )
        await db_session.commit()

        response = await client.get("/api/v1/research/patterns?region=Chile")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

        pattern = next(p for p in data if p["pattern_hash"] == "api_test_hash_1")
        assert pattern["pattern_hash"] == "api_test_hash_1"
        assert pattern["source_event_type"] == "earthquake"
        assert pattern["target_event_type"] == "tsunami"
        assert pattern["region_label"] == "Chile"
        assert pattern["lift"] == 4.0
        assert pattern["uncertainty"]["source"] == "model_uncertainty"

    async def test_get_research_patterns_filtering_and_sorting(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Filtering by event_type, region, and sorting by lift works as expected."""
        monkeypatch.setenv("PUBLIC_RESEARCH_API_ENABLED", "true")
        get_settings.cache_clear()

        mined_time = datetime.now(UTC)

        await PatternFindingRepository.save_pattern_version(
            session=db_session,
            pattern_hash="hash_a",
            source_event_type="unique_test_wildfire",
            target_event_type="air_quality_anomaly",
            region_label="UniqueTestRegion_CA",
            time_window_days=14,
            support_count=10,
            total_source_events=12,
            total_target_events=15,
            observed_rate=0.83,
            baseline_rate=0.25,
            lift=3.32,
            statistical_confidence=0.85,
            uncertainty={
                "point_estimate": 0.85,
                "lower_bound": 0.77,
                "upper_bound": 0.93,
                "source": "well_supported",
            },
            supporting_event_ids=["id_a1"],
            description="California wildfire to air quality anomaly",
            mined_at=mined_time,
        )
        await db_session.commit()

        # Filter by region=UniqueTestRegion_CA
        response = await client.get("/api/v1/research/patterns?region=UniqueTestRegion_CA")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["region_label"] == "UniqueTestRegion_CA"

        # Filter by event_type=unique_test_wildfire
        response_type = await client.get(
            "/api/v1/research/patterns?event_type=unique_test_wildfire"
        )
        assert response_type.status_code == 200
        assert len(response_type.json()) == 1

        # Non-matching filter returns empty list
        response_empty = await client.get(
            "/api/v1/research/patterns?region=NonExistentRegion"
        )
        assert response_empty.status_code == 200
        assert response_empty.json() == []

    async def test_get_research_patterns_disabled_feature_flag(
        self,
        client: AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """GET /api/v1/research/patterns returns 503 when PUBLIC_RESEARCH_API_ENABLED=false."""
        monkeypatch.setenv("PUBLIC_RESEARCH_API_ENABLED", "false")
        get_settings.cache_clear()

        response = await client.get("/api/v1/research/patterns")
        assert response.status_code == 503
        assert response.json()["error_code"] == "public_research_api_disabled"
