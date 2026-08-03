"""Unit and integration tests for ERA5 atmospheric reanalysis baseline ingestion."""

from __future__ import annotations

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock

import pytest
import respx

from ingestion.scheduled.hazard_event_sources.era5_atmospheric import fetch_recent_era5_events
from tools.era5.client import ERA5Client

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
async def test_era5_client_and_adapter_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify ERA5 client fetches atmospheric baselines and adapter maps to HazardEventRecord with details attribution."""
    fake_redis = _InMemoryRedis()
    monkeypatch.setattr("resilience.degraded_mode.get_redis", AsyncMock(return_value=fake_redis))
    monkeypatch.setattr("resilience.circuit_breaker.get_redis", AsyncMock(return_value=fake_redis))

    mock_response = {
        "daily": {
            "time": ["2026-07-24"],
            "temperature_2m_mean": [22.5],
            "wind_speed_10m_max": [18.2],
            "precipitation_sum": [4.5],
        }
    }

    respx.get(url__startswith="https://archive-api.open-meteo.com/v1/archive").respond(
        json=mock_response,
        status_code=200,
    )

    client = ERA5Client()
    res = await client.get_atmospheric_baseline(
        lat=35.6762,
        lon=139.6503,
        start_date=date(2026, 7, 24),
        end_date=date(2026, 7, 24),
    )

    assert res.degraded is False
    assert res.source_status == "live"
    assert res.value["daily"]["temperature_2m_mean"] == [22.5]

    records = await fetch_recent_era5_events(since=datetime(2026, 7, 20, tzinfo=UTC))
    assert len(records) > 0
    rec = records[0]
    assert rec.source == "era5"
    assert "era5_" in rec.external_id
    assert rec.event_type == "atmospheric_anomaly"
    assert "ECMWF ERA5" in rec.details
    assert "Source URL:" in rec.details


@pytest.mark.asyncio
@respx.mock
async def test_era5_ingestion_job_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify ERA5 ingestion job respects feature flag when disabled."""
    from config.settings import get_settings
    from workers.jobs.ingestion_jobs import _async_run_ingestion_job

    monkeypatch.setattr(get_settings(), "enable_era5_ingestion", False)

    res = await _async_run_ingestion_job("era5")
    assert res["status"] == "disabled"
    assert res["records_inserted"] == 0
