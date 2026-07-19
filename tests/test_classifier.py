"""Tests for query complexity classification and fallback routing."""

from __future__ import annotations

import pytest

from orchestrator.agents.supervisor.classifier import classify_query_complexity
from orchestrator.agents.supervisor.planner import classify_query
from orchestrator.schemas.complexity import ComplexityTier


class TestClassifier:
    """Verifies that query classification rules and priority routing work correctly."""

    async def test_classify_trivial_queries(self) -> None:
        result = await classify_query_complexity(
            "What is the current air quality in Paris?"
        )
        assert result["tier"] == ComplexityTier.TRIVIAL
        assert "air_quality" in result["matched_domains"]

        result = await classify_query_complexity("pm2.5 levels in Beijing")
        assert result["tier"] == ComplexityTier.TRIVIAL
        assert "air_quality" in result["matched_domains"]

    async def test_classify_moderate_queries(self) -> None:
        result = await classify_query_complexity(
            "Show me seismic activity and air quality in Tokyo"
        )
        assert result["tier"] == ComplexityTier.MODERATE
        assert "seismic" in result["matched_domains"]
        assert "air_quality" in result["matched_domains"]

        result = await classify_query_complexity("wildfire status in California")
        assert result["tier"] == ComplexityTier.MODERATE
        assert "wildfire" in result["matched_domains"]

    async def test_classify_complex_queries(self) -> None:
        result = await classify_query_complexity(
            "Predict if an earthquake will trigger a tsunami"
        )
        assert result["tier"] == ComplexityTier.COMPLEX
        assert "seismic" in result["matched_domains"]
        assert "ocean" in result["matched_domains"]

        result = await classify_query_complexity(
            "simulated plume dispersion forecast for Madrid"
        )
        assert result["tier"] == ComplexityTier.COMPLEX

    async def test_ambiguous_priority_overrides(self) -> None:
        # Mixed trivial ("air quality") and complex ("predict") triggers COMPLEX
        result = await classify_query_complexity("Predict the air quality for tomorrow")
        assert result["tier"] == ComplexityTier.COMPLEX

        # Mixed trivial ("pm2.5") and moderate ("seismic") triggers MODERATE
        result = await classify_query_complexity("seismic and pm2.5 metrics")
        assert result["tier"] == ComplexityTier.MODERATE

    async def test_planner_exception_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Mock classify_query_complexity to raise an exception
        async def mock_classify_error(query: str):
            raise RuntimeError("Mocked classifier error.")

        import orchestrator.agents.supervisor.planner as planner_mod
        monkeypatch.setattr(planner_mod, "classify_query_complexity", mock_classify_error)

        tier = await classify_query("any query text")
        assert tier == ComplexityTier.MODERATE
