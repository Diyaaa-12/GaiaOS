"""Tests for the Seismic domain agent and USGS client."""

from __future__ import annotations

import uuid

import respx

from orchestrator.agents.seismic.agent import run as run_seismic
from orchestrator.schemas.agent_io import AgentInput


class TestSeismicAgent:
    """Verifies evidence parsing and error tolerance of the Seismic agent."""

    @respx.mock
    async def test_agent_success(self) -> None:
        # Mock USGS earthquake query endpoint
        respx.get("https://earthquake.usgs.gov/fdsnws/event/1/query").respond(
            json={
                "features": [
                    {
                        "properties": {
                            "mag": 5.4,
                            "place": "10km E of Tokyo, Japan",
                            "time": 1782000000000,
                        }
                    }
                ]
            },
            status_code=200,
        )

        inp = AgentInput(
            investigation_id=uuid.uuid4(),
            query="Seismic readings for Tokyo",
            region_hint="Tokyo",
        )

        output = await run_seismic(inp)
        assert output.agent_name == "seismic"
        assert len(output.errors) == 0
        assert len(output.evidence) == 1

        claim = output.evidence[0].claim
        assert "5.4" in claim
        assert "Tokyo" in claim
        assert output.evidence[0].source == "USGS Seismic API"

    @respx.mock
    async def test_agent_no_results(self) -> None:
        respx.get("https://earthquake.usgs.gov/fdsnws/event/1/query").respond(
            json={"features": []},
            status_code=200,
        )

        inp = AgentInput(
            investigation_id=uuid.uuid4(),
            query="Earthquakes in Paris",
            region_hint="Paris",
        )

        output = await run_seismic(inp)
        assert len(output.evidence) == 0
        assert len(output.errors) == 1
        assert "No recent earthquakes found" in output.errors[0]

    @respx.mock
    async def test_agent_api_error(self) -> None:
        respx.get("https://earthquake.usgs.gov/fdsnws/event/1/query").respond(
            status_code=500,
            text="Internal Server Error",
        )

        inp = AgentInput(
            investigation_id=uuid.uuid4(),
            query="Earthquakes in Tokyo",
            region_hint="Tokyo",
        )

        output = await run_seismic(inp)
        assert len(output.evidence) == 0
        assert len(output.errors) == 1
        assert "Failed to query USGS" in output.errors[0]
