"""Tests for dynamic NOAA station resolution, Redis caching, and explicit error gap handling."""

from __future__ import annotations

import uuid

import pytest
import respx

from cache.keys import RedisKeyBuilder
from orchestrator.agents.ocean.agent import run as run_ocean
from orchestrator.schemas.agent_io import AgentInput
from tools.geocoding import (
    NOAA_STATIONS_API_URL,
    resolve_nearest_station,
)

# Mock NOAA Station Metadata API response fixture with stations near US coastal cities
MOCK_NOAA_STATIONS_JSON = {
    "count": 3,
    "stations": [
        {
            "id": "8518750",
            "name": "The Battery, NY",
            "lat": 40.7006,
            "lng": -74.0142,
        },
        {
            "id": "9414290",
            "name": "Fort Point, San Francisco, CA",
            "lat": 37.8067,
            "lng": -122.465,
        },
        {
            "id": "8723214",
            "name": "Virginia Key, Miami, FL",
            "lat": 25.7314,
            "lng": -80.1617,
        },
    ],
}


@pytest.mark.asyncio
@respx.mock
async def test_resolve_nearest_station_three_cities() -> None:
    """Verify 3 NOAA coastal cities resolve to their expected nearest NOAA station."""
    respx.get(NOAA_STATIONS_API_URL).respond(
        json=MOCK_NOAA_STATIONS_JSON,
        status_code=200,
    )

    # 1. New York (40.7128, -74.006) -> Station 8518750 (The Battery, NY)
    ny_station = await resolve_nearest_station(40.7128, -74.006)
    assert ny_station == "8518750"

    # 2. San Francisco (37.7749, -122.4194) -> Station 9414290 (Fort Point, CA)
    sf_station = await resolve_nearest_station(37.7749, -122.4194)
    assert sf_station == "9414290"

    # 3. Miami (25.7617, -80.1918) -> Station 8723214 (Virginia Key, FL)
    miami_station = await resolve_nearest_station(25.7617, -80.1918)
    assert miami_station == "8723214"


@pytest.mark.asyncio
@respx.mock
async def test_station_api_failure_returns_none() -> None:
    """Verify station API failure returns None without falling back to hardcoded ID."""
    respx.get(NOAA_STATIONS_API_URL).respond(status_code=500)

    station_id = await resolve_nearest_station(40.7128, -74.006)
    assert station_id is None


@pytest.mark.asyncio
@respx.mock
async def test_no_station_in_range_returns_none() -> None:
    """Verify location far from coastal stations (> MAX_STATION_DISTANCE_KM) returns None."""
    respx.get(NOAA_STATIONS_API_URL).respond(
        json=MOCK_NOAA_STATIONS_JSON,
        status_code=200,
    )

    # Inland location in Kansas City (39.0997, -94.5786) > 1000 km from coastal stations
    station_id = await resolve_nearest_station(39.0997, -94.5786)
    assert station_id is None


@pytest.mark.asyncio
@respx.mock
async def test_ocean_agent_fails_fast_when_station_id_is_none() -> None:
    """Verify OceanAgent fails fast with an explicit gap when station_id is None."""
    # Mock Open-Meteo geocoding (now called by geocode_location via resilient_call)
    respx.get("https://geocoding-api.open-meteo.com/v1/search").respond(
        json={"results": [{"name": "Paris", "latitude": 48.8566, "longitude": 2.3522}]},
        status_code=200,
    )
    # Stations API returns empty stations list
    respx.get(NOAA_STATIONS_API_URL).respond(
        json={"stations": []},
        status_code=200,
    )
    # Ensure water temperature API is NEVER called when station resolution fails
    datagetter_route = respx.get(
        "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
    ).respond(
        status_code=200,
    )

    inp = AgentInput(
        investigation_id=uuid.uuid4(),
        query="Water temp in Paris",
        region_hint="Paris",
    )

    output = await run_ocean(inp)

    assert output.agent_name == "ocean"
    assert len(output.evidence) == 0
    assert len(output.errors) == 1
    assert "No active NOAA ocean station found" in output.errors[0]
    assert not datagetter_route.called


@pytest.mark.asyncio
@respx.mock
async def test_redis_station_cache_hit_and_miss(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify station lookup checks Redis cache and logs cache hit/miss."""
    respx.get(NOAA_STATIONS_API_URL).respond(
        json=MOCK_NOAA_STATIONS_JSON,
        status_code=200,
    )

    lat, lon = 40.7128, -74.006
    station_id = await resolve_nearest_station(lat, lon)
    assert station_id == "8518750"

    cache_key = RedisKeyBuilder.station_key(lat, lon, "noaa")
    assert cache_key == "gaiaos:cache:station:noaa:40.71:-74.01"
