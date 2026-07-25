"""Unit tests for the NOAA historical hazard event source adapter."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
import respx

from ingestion.scheduled.hazard_event_sources.noaa_historical import fetch_recent_noaa_events


@pytest.mark.asyncio
async def test_fetch_recent_noaa_events_mapping() -> None:
    """Verify raw NOAA water temperature JSON payload is mapped to HazardEventRecord instances."""
    mock_noaa_json = {
        "data": [
            {
                "t": "2026-07-25 12:00",
                "v": "24.5",
            }
        ]
    }

    with respx.mock(assert_all_called=False) as respx_mock:
        respx_mock.get(url__startswith="https://api.tidesandcurrents.noaa.gov").respond(
            status_code=200,
            json=mock_noaa_json,
        )

        since = datetime(2026, 7, 24, tzinfo=UTC)
        records = await fetch_recent_noaa_events(since=since)

        assert len(records) > 0
        rec = records[0]
        assert rec.source == "noaa"
        assert rec.external_id.startswith("noaa_")
        assert rec.event_type == "marine heatwave"
        assert "water temperature: 24.5°C" in (rec.details or "")
