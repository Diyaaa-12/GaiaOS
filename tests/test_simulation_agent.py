"""Tests for the Simulation domain agent."""

from __future__ import annotations

import uuid

import pytest

from orchestrator.agents.simulation.agent import run as run_simulation_agent
from orchestrator.agents.supervisor.classifier import classify_query_complexity
from orchestrator.schemas.agent_io import AgentInput, AgentOutput, Evidence


class TestSimulationAgent:
    """Verifies evidence parsing, parameters parsing, bounds checks, and registry routing."""

    @pytest.mark.asyncio
    async def test_agent_success_with_prior_evidence(self) -> None:
        """Verify parameters are correctly parsed from prior Atmosphere evidence."""
        prior_ev = Evidence(
            source="Open-Meteo Weather API",
            claim=(
                "Current atmospheric conditions: Temperature is 25.5°C, "
                "Wind Speed is 15.0 km/h, and Relative Humidity is 60%."
            ),
            confidence=0.95,
        )
        prior_output = AgentOutput(agent_name="atmosphere", evidence=[prior_ev])

        inp = AgentInput(
            investigation_id=uuid.uuid4(),
            query="Simulate wildfire spread rate",
        )

        # Run agent
        output = await run_simulation_agent(inp, [prior_output])

        assert output.agent_name == "simulation"
        assert len(output.errors) == 0
        assert len(output.evidence) == 1
        assert "WildfireSpreadModel" in output.evidence[0].source
        assert output.evidence[0].claim is not None
        assert output.evidence[0].uncertainty_bounds is not None
        assert len(output.evidence[0].assumptions) > 0

    @pytest.mark.asyncio
    async def test_agent_success_with_query_extraction(self) -> None:
        """Verify parameters are extracted from query when prior evidence is missing."""
        inp = AgentInput(
            investigation_id=uuid.uuid4(),
            query="Forecast ENSO with sst anomaly of 1.2 C",
        )

        output = await run_simulation_agent(inp, [])

        assert output.agent_name == "simulation"
        assert len(output.errors) == 0
        assert len(output.evidence) == 1
        assert "El Niño" in output.evidence[0].claim
        assert output.evidence[0].uncertainty_bounds == pytest.approx((1.0, 1.4))

    @pytest.mark.asyncio
    async def test_missing_input_parameter_error(self) -> None:
        """Verify missing parameters result in explicit parameter errors."""
        inp = AgentInput(
            investigation_id=uuid.uuid4(),
            query="Predict plume dispersion in London",  # no wind speed specified
        )

        output = await run_simulation_agent(inp, [])
        assert output.agent_name == "simulation"
        assert len(output.evidence) == 0
        assert len(output.errors) == 1
        assert "Missing required input" in output.errors[0]

    @pytest.mark.asyncio
    async def test_sanity_bound_checker_failure(self) -> None:
        """Verify out of bounds parameters result in 'simulation inconclusive'."""
        inp = AgentInput(
            investigation_id=uuid.uuid4(),
            query="Predict flood extent for rainfall 600 mm",  # out of bounds (max 500)
        )

        output = await run_simulation_agent(inp, [])
        assert output.agent_name == "simulation"
        assert len(output.evidence) == 0
        assert len(output.errors) == 1
        assert output.errors[0] == "simulation inconclusive"


class TestSimulationPlannerGate:
    """Verifies that query classification flags prediction queries for simulation routing."""

    @pytest.mark.asyncio
    async def test_needs_simulation_flagged(self) -> None:
        res1 = await classify_query_complexity("Forecast ENSO conditions under SST anomaly 1.5 C")
        assert res1["needs_simulation"] is True

        res2 = await classify_query_complexity("Predict wildfire spread rate and plume dispersion")
        assert res2["needs_simulation"] is True

    @pytest.mark.asyncio
    async def test_needs_simulation_not_flagged_for_factual(self) -> None:
        res = await classify_query_complexity(
            "What is the current air quality and wind speed in Paris?"
        )
        assert res["needs_simulation"] is False
