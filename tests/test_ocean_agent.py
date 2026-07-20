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
