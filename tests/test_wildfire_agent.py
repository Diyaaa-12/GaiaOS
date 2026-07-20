"""Tests for the Wildfire domain agent and FIRMS client."""

from __future__ import annotations

import uuid

import pytest
import respx

from orchestrator.agents.wildfire.agent import run as run_wildfire
from orchestrator.schemas.agent_io import AgentInput


class TestWildfireAgent:
    """Verifies evidence parsing and error tolerance of the Wildfire agent."""

    @respx.mock
    async def test_agent_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Mock FIRMS API key in settings
        from config.settings import get_settings

        monkeypatch.setattr(get_settings(), "firms_api_key", "mock_key")

        # Mock CSV response from FIRMS API
        csv_data = (
            "latitude,longitude,brightness,scan,track,acq_date,acq_time,satellite,instrument,"
            "confidence,version,bright_t31,frp,daynight\n"
            "37.5,-120.5,310.2,1.0,1.0,2026-07-20,0845,T,MODIS,100,6.0,290.1,12.5,D\n"
        )
        respx.get(
            url__startswith="https://firms.modaps.eosdis.nasa.gov/api/area/csv"
        ).respond(
            text=csv_data,
            status_code=200,
        )

        inp = AgentInput(
            investigation_id=uuid.uuid4(),
            query="Wildfires in California",
            region_hint="California",
        )

        output = await run_wildfire(inp)
        assert output.agent_name == "wildfire"
        assert len(output.errors) == 0
        assert len(output.evidence) == 1

        claim = output.evidence[0].claim
        assert "Active fire detected" in claim
        assert "California" in claim
        assert "NASA FIRMS API" in output.evidence[0].source
        assert output.evidence[0].confidence == 0.90

    @respx.mock
    async def test_agent_missing_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from config.settings import get_settings

        monkeypatch.setattr(get_settings(), "firms_api_key", None)

        inp = AgentInput(
            investigation_id=uuid.uuid4(),
            query="Wildfires in California",
            region_hint="California",
        )

        output = await run_wildfire(inp)
        assert len(output.evidence) == 0
        assert len(output.errors) == 1
        assert "NASA FIRMS API key is not configured" in output.errors[0]

    @respx.mock
    async def test_agent_api_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from config.settings import get_settings

        monkeypatch.setattr(get_settings(), "firms_api_key", "mock_key")

        respx.get(
            url__startswith="https://firms.modaps.eosdis.nasa.gov/api/area/csv"
        ).respond(
            status_code=500,
        )

        inp = AgentInput(
            investigation_id=uuid.uuid4(),
            query="Wildfires in California",
            region_hint="California",
        )

        output = await run_wildfire(inp)
        assert len(output.evidence) == 0
        assert len(output.errors) == 1
        assert "Failed to query FIRMS wildfire API" in output.errors[0]
