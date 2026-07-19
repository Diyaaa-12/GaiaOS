"""Tests for orchestrator schemas validation."""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from orchestrator.schemas.agent_io import AgentInput, AgentOutput, Evidence
from orchestrator.schemas.complexity import ComplexityTier


class TestSchemasValidation:
    """Verifies that schemas enforce standard constraints correctly."""

    def test_evidence_valid(self) -> None:
        ev = Evidence(
            source="test",
            claim="PM2.5 is high",
            confidence=0.85,
        )
        assert ev.source == "test"
        assert ev.confidence == 0.85

    def test_evidence_invalid_confidence_high(self) -> None:
        with pytest.raises(ValidationError):
            Evidence(
                source="test",
                claim="PM2.5 is high",
                confidence=1.1,
            )

    def test_evidence_invalid_confidence_low(self) -> None:
        with pytest.raises(ValidationError):
            Evidence(
                source="test",
                claim="PM2.5 is high",
                confidence=-0.1,
            )

    def test_agent_input_valid(self) -> None:
        uid = uuid.uuid4()
        inp = AgentInput(
            investigation_id=uid,
            query="Paris Air Quality",
            region_hint="Paris",
        )
        assert inp.investigation_id == uid
        assert inp.query == "Paris Air Quality"
        assert inp.region_hint == "Paris"

    def test_agent_output_valid(self) -> None:
        ev = Evidence(
            source="test",
            claim="PM2.5 is high",
            confidence=0.85,
        )
        out = AgentOutput(
            agent_name="air_quality",
            evidence=[ev],
            errors=["Station unavailable"],
        )
        assert out.agent_name == "air_quality"
        assert len(out.evidence) == 1
        assert out.errors == ["Station unavailable"]

    def test_complexity_tier_values(self) -> None:
        assert ComplexityTier.TRIVIAL == "trivial"
        assert ComplexityTier.MODERATE == "moderate"
        assert ComplexityTier.COMPLEX == "complex"
