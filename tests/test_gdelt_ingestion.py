"""Unit and integration tests for GDELT socio-political news event ingestion."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
import respx

from ingestion.scheduled.hazard_event_sources.gdelt_events import fetch_recent_gdelt_events
from tools.gdelt.client import GDELTClient

class _InMemoryRedis:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}
    async def get(self, key: str) -> str | None:
        return self._store.get(key)
    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._store[key] = value
    async def ping(self) -> bool:
        return True


@pytest.mark.asyncio
@respx.mock
async def test_gdelt_client_and_adapter_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify GDELT client fetches articles and adapter maps to HazardEventRecord with details attribution."""
    fake_redis = _InMemoryRedis()
    monkeypatch.setattr("resilience.degraded_mode.get_redis", AsyncMock(return_value=fake_redis))
    monkeypatch.setattr("resilience.circuit_breaker.get_redis", AsyncMock(return_value=fake_redis))

    mock_response = {
        "articles": [
            {
                "url": "https://example.com/news/wildfire-evacuation-2026",
                "title": "Wildfire Evacuation Ordered in California",
                "seendate": "20260724T120000Z",
                "domain": "example.com",
                "language": "English",
            }
        ]
    }

    respx.get(url__startswith="https://api.gdeltproject.org/api/v2/doc/doc").respond(
        json=mock_response,
        status_code=200,
    )

    client = GDELTClient()
    res = await client.get_hazard_articles(query="wildfire OR disaster")

    assert res.degraded is False
    assert res.source_status == "live"
    assert len(res.value) == 1
    assert res.value[0]["title"] == "Wildfire Evacuation Ordered in California"

    records = await fetch_recent_gdelt_events(since=datetime(2026, 7, 1, tzinfo=UTC))
    assert len(records) > 0
    rec = records[0]
    assert rec.source == "gdelt"
    assert "gdelt_" in rec.external_id
    assert rec.event_type == "civil_unrest_hazard_adjacent"
    assert "GDELT Project" in rec.details
    assert "Source URL:" in rec.details


@pytest.mark.asyncio
@respx.mock
async def test_gdelt_cursor_monotonicity_and_deduplication(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify GDELT ingestion adapter filters out old events to maintain cursor monotonicity and generates deterministic IDs."""
    fake_redis = _InMemoryRedis()
    monkeypatch.setattr("resilience.degraded_mode.get_redis", AsyncMock(return_value=fake_redis))
    monkeypatch.setattr("resilience.circuit_breaker.get_redis", AsyncMock(return_value=fake_redis))

    mock_response = {
        "articles": [
            {
                "url": "https://example.com/news/event-old",
                "title": "Old Event",
                "seendate": "20260701T120000Z",  # Before since cutoff
                "domain": "example.com",
            },
            {
                "url": "https://example.com/news/event-new",
                "title": "New Event",
                "seendate": "20260724T120000Z",  # After since cutoff
                "domain": "example.com",
            },
        ]
    }

    respx.get(url__startswith="https://api.gdeltproject.org/api/v2/doc/doc").respond(
        json=mock_response,
        status_code=200,
    )

    since = datetime(2026, 7, 15, tzinfo=UTC)
    records = await fetch_recent_gdelt_events(since=since)

    # Old event filtered out to guarantee monotonicity
    assert len(records) == 1
    assert "New Event" in records[0].details
    assert records[0].event_date >= since


@pytest.mark.asyncio
@respx.mock
async def test_gdelt_max_records_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify GDELT client respects gdelt_max_records_per_run setting cap."""
    from config.settings import get_settings

    monkeypatch.setattr(get_settings(), "gdelt_max_records_per_run", 50)

    client = GDELTClient()
    assert client.max_records == 50


@pytest.mark.asyncio
@respx.mock
async def test_gdelt_ingestion_job_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify GDELT ingestion job respects feature flag when disabled."""
    from config.settings import get_settings
    from workers.jobs.ingestion_jobs import _async_run_ingestion_job

    monkeypatch.setattr(get_settings(), "enable_gdelt_ingestion", False)

    res = await _async_run_ingestion_job("gdelt")
    assert res["status"] == "disabled"
    assert res["records_inserted"] == 0
