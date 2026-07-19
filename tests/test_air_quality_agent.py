"""Tests for the Air Quality domain agent and OpenAQ client."""

from __future__ import annotations

import uuid

import respx

from orchestrator.agents.air_quality.agent import run as run_air_quality
from orchestrator.schemas.agent_io import AgentInput


class TestAirQualityAgent:
    """Verifies evidence parsing and error tolerance of the Air Quality agent."""

    @respx.mock
    async def test_agent_success(self) -> None:
        # Mock OpenAQ latest endpoint
        respx.get("https://api.openaq.org/v2/latest").respond(
            json={
                "results": [
                    {
                        "location": "Paris-Centre",
                        "measurements": [
                            {"parameter": "pm25", "value": 12.0, "unit": "ug/m3"},
                            {"parameter": "pm10", "value": 24.0, "unit": "ug/m3"},
                        ],
                    }
                ]
            },
            status_code=200,
        )

        inp = AgentInput(
            investigation_id=uuid.uuid4(),
            query="Paris PM2.5 levels?",
            region_hint="Paris",
        )

        output = await run_air_quality(inp)
        assert output.agent_name == "air_quality"
        assert len(output.errors) == 0
        assert len(output.evidence) == 2

        # Check evidence claims
        claim1 = output.evidence[0].claim
        assert "Paris-Centre" in claim1
        assert "pm25" in claim1
        assert "12.0" in claim1

    @respx.mock
    async def test_agent_no_stations(self) -> None:
        respx.get("https://api.openaq.org/v2/latest").respond(
            json={"results": []},
            status_code=200,
        )

        inp = AgentInput(
            investigation_id=uuid.uuid4(),
            query="Query with no stations",
            region_hint="Atlantis",
        )

        output = await run_air_quality(inp)
        assert len(output.evidence) == 0
        assert "No active OpenAQ stations found" in output.errors[0]

    @respx.mock
    async def test_agent_error_fallback(self) -> None:
        respx.get("https://api.openaq.org/v2/latest").respond(
            status_code=500,
            text="Internal Server Error",
        )

        inp = AgentInput(
            investigation_id=uuid.uuid4(),
            query="Paris Air Quality",
            region_hint="Paris",
        )

        output = await run_air_quality(inp)
        assert len(output.evidence) == 0
        assert len(output.errors) == 1
        assert "Failed to query OpenAQ" in output.errors[0]
