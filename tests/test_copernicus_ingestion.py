"""Unit and integration tests for Copernicus Sentinel satellite metadata ingestion."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from unittest.mock import AsyncMock

import pytest
import respx

from ingestion.scheduled.hazard_event_sources.copernicus_wildfire import fetch_recent_copernicus_events
from tools.copernicus_sentinel.client import CopernicusSentinelClient

# Inline FakeRedis helper for tests
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
async def test_copernicus_client_and_adapter_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify Copernicus client fetches product metadata and adapter maps to HazardEventRecord with details attribution."""
    fake_redis = _InMemoryRedis()
    monkeypatch.setattr("resilience.degraded_mode.get_redis", AsyncMock(return_value=fake_redis))
    monkeypatch.setattr("resilience.circuit_breaker.get_redis", AsyncMock(return_value=fake_redis))

    mock_response = {
        "value": [
            {
                "Id": "prod_sentinel2_001",
                "Name": "S2B_MSIL1C_20260724T101500_California_Wildfire",
                "ContentDate": {"Start": "2026-07-24T10:15:00.000Z"},
            }
        ]
    }

    respx.get(url__startswith="https://catalogue.dataspace.copernicus.eu/odata/v1/Products").respond(
        json=mock_response,
        status_code=200,
    )

    client = CopernicusSentinelClient()
    res = await client.get_wildfire_products(min_x=-124.0, min_y=32.0, max_x=-114.0, max_y=42.0)

    assert res.degraded is False
    assert res.source_status == "live"
    assert len(res.value) == 1
    assert res.value[0]["Id"] == "prod_sentinel2_001"

    records = await fetch_recent_copernicus_events(since=datetime(2026, 7, 20, tzinfo=UTC))
    assert len(records) > 0
    rec = records[0]
    assert rec.source == "copernicus"
    assert "copernicus_" in rec.external_id
    assert rec.event_type == "wildfire_satellite"
    assert "EU Copernicus Data Space" in rec.details
    assert "Source URL:" in rec.details


@pytest.mark.asyncio
@respx.mock
async def test_copernicus_ingestion_job_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify copernicus ingestion job respects feature flag when disabled."""
    from config.settings import get_settings
    from workers.jobs.ingestion_jobs import _async_run_ingestion_job

    monkeypatch.setattr(get_settings(), "enable_copernicus_ingestion", False)

    res = await _async_run_ingestion_job("copernicus")
    assert res["status"] == "disabled"
    assert res["records_inserted"] == 0
