"""Tests for the Ocean domain agent and NOAA client."""

from __future__ import annotations

import uuid

import respx

from orchestrator.agents.ocean.agent import run as run_ocean
from orchestrator.schemas.agent_io import AgentInput


class TestOceanAgent:
    """Verifies evidence parsing and error tolerance of the Ocean agent."""

    @respx.mock
    async def test_agent_success(self) -> None:
        # Mock Open-Meteo geocoding (now called by geocode_location via resilient_call)
        respx.get("https://geocoding-api.open-meteo.com/v1/search").respond(
            json={"results": [{"name": "Tokyo", "latitude": 35.6762, "longitude": 139.6503}]},
            status_code=200,
        )
        # Mock NOAA stations metadata (called by resolve_nearest_station via resilient_call)
        respx.get("https://api.tidesandcurrents.noaa.gov/mdapi/v1.0/webapi/stations.json").respond(
            json={
                "stations": [{"id": "9759110", "name": "Tokyo Bay", "lat": 35.65, "lng": 139.75}]
            },
            status_code=200,
        )
        respx.get("https://api.tidesandcurrents.noaa.gov/api/prod/datagetter").respond(
            json={"data": [{"t": "2026-07-20 12:00", "v": "18.5"}]},
            status_code=200,
        )

        inp = AgentInput(
            investigation_id=uuid.uuid4(),
            query="Water temp in Tokyo",
            region_hint="Tokyo",
        )

        output = await run_ocean(inp)
        assert output.agent_name == "ocean"
        assert len(output.errors) == 0
        assert len(output.evidence) == 1

        claim = output.evidence[0].claim
        assert "18.5" in claim
        assert "Tokyo" in claim
        assert "NOAA Ocean API" in output.evidence[0].source

    @respx.mock
    async def test_agent_no_results(self) -> None:
        # Mock Open-Meteo geocoding
        respx.get("https://geocoding-api.open-meteo.com/v1/search").respond(
            json={"results": [{"name": "Paris", "latitude": 48.8566, "longitude": 2.3522}]},
            status_code=200,
        )
        # Mock NOAA stations metadata
        respx.get("https://api.tidesandcurrents.noaa.gov/mdapi/v1.0/webapi/stations.json").respond(
            json={"stations": [{"id": "8518750", "name": "Le Havre", "lat": 49.49, "lng": 0.10}]},
            status_code=200,
        )
        respx.get("https://api.tidesandcurrents.noaa.gov/api/prod/datagetter").respond(
            json={"error": "No data found"},
            status_code=200,
        )

        inp = AgentInput(
            investigation_id=uuid.uuid4(),
            query="Water temp in Paris",
            region_hint="Paris",
        )

        output = await run_ocean(inp)
        assert len(output.evidence) == 0
        assert len(output.errors) == 1
        assert "No active NOAA ocean measurements found" in output.errors[0]

    @respx.mock
    async def test_agent_api_error(self) -> None:
        respx.get("https://api.tidesandcurrents.noaa.gov/mdapi/v1.0/webapi/stations.json").respond(
            json={
                "stations": [{"id": "9759110", "name": "Tokyo Bay", "lat": 35.65, "lng": 139.75}]
            },
            status_code=200,
        )
        respx.get("https://api.tidesandcurrents.noaa.gov/api/prod/datagetter").respond(
            status_code=500,
        )

        inp = AgentInput(
            investigation_id=uuid.uuid4(),
            query="Water temp in Tokyo",
            region_hint="Tokyo",
        )

        output = await run_ocean(inp)
        assert len(output.evidence) == 0
        assert len(output.errors) == 1
        assert "Failed to query NOAA" in output.errors[0]
