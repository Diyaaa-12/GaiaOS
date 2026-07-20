"""Tests for the Atmosphere domain agent and Weather client."""

from __future__ import annotations

import uuid

import respx

from orchestrator.agents.atmosphere.agent import run as run_atmosphere
from orchestrator.schemas.agent_io import AgentInput


class TestAtmosphereAgent:
    """Verifies evidence parsing and error tolerance of the Atmosphere agent."""

    @respx.mock
    async def test_agent_success(self) -> None:
        respx.get("https://api.open-meteo.com/v1/forecast").respond(
            json={
                "current": {
                    "temperature_2m": 22.1,
                    "wind_speed_10m": 15.4,
                    "relative_humidity_2m": 60,
                }
            },
            status_code=200,
        )

        inp = AgentInput(
            investigation_id=uuid.uuid4(),
            query="Weather in London",
            region_hint="London",
        )

        output = await run_atmosphere(inp)
        assert output.agent_name == "atmosphere"
        assert len(output.errors) == 0
        assert len(output.evidence) == 1

        claim = output.evidence[0].claim
        assert "22.1" in claim
        assert "15.4" in claim
        assert "60%" in claim
        assert "Open-Meteo Weather API" in output.evidence[0].source

    @respx.mock
    async def test_agent_no_results(self) -> None:
        respx.get("https://api.open-meteo.com/v1/forecast").respond(
            json={},
            status_code=200,
        )

        inp = AgentInput(
            investigation_id=uuid.uuid4(),
            query="Weather in London",
            region_hint="London",
        )

        output = await run_atmosphere(inp)
        assert len(output.evidence) == 0
        assert len(output.errors) == 1
        assert "No atmospheric data returned" in output.errors[0]

    @respx.mock
    async def test_agent_api_error(self) -> None:
        respx.get("https://api.open-meteo.com/v1/forecast").respond(
            status_code=500,
        )

        inp = AgentInput(
            investigation_id=uuid.uuid4(),
            query="Weather in Tokyo",
            region_hint="Tokyo",
        )

        output = await run_atmosphere(inp)
        assert len(output.evidence) == 0
        assert len(output.errors) == 1
        assert "Failed to query Open-Meteo weather" in output.errors[0]
