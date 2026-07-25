"""Unit tests for the USGS historical hazard event source adapter."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
import respx

from ingestion.scheduled.hazard_event_sources.usgs_historical import fetch_recent_usgs_events


@pytest.mark.asyncio
async def test_fetch_recent_usgs_events_mapping() -> None:
    """Verify raw USGS GeoJSON features are mapped to HazardEventRecord instances."""
    mock_geojson = {
        "features": [
            {
                "id": "us7000test",
                "properties": {
                    "place": "10 km S of Tokyo, Japan",
                    "mag": 5.4,
                    "time": 1721836800000,  # Epoch ms
                },
                "geometry": {
                    "coordinates": [139.6503, 35.6762, 10.0],
                },
            }
        ]
    }

    with respx.mock(assert_all_called=False) as respx_mock:
        respx_mock.get(url__startswith="https://earthquake.usgs.gov").respond(
            status_code=200,
            json=mock_geojson,
        )

        since = datetime(2026, 7, 24, tzinfo=UTC)
        records = await fetch_recent_usgs_events(since=since, min_magnitude=2.0)

        assert len(records) == 1
        rec = records[0]
        assert rec.source == "usgs"
        assert rec.external_id == "us7000test"
        assert rec.event_type == "earthquake"
        assert rec.region_label == "10 km S of Tokyo, Japan"
        assert rec.point == (35.6762, 139.6503)
        assert rec.details == "Magnitude 5.4 earthquake - 10 km S of Tokyo, Japan"
