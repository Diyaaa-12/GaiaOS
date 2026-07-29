"""Unit and integration tests for UncertaintyEstimate (Phase 5 Milestone 3)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from orchestrator.agents.synthesis.agent import synthesize
from orchestrator.agents.synthesis.uncertainty_propagation import propagate_uncertainty
from orchestrator.schemas.agent_io import AgentOutput, Evidence
from orchestrator.schemas.uncertainty import UncertaintyEstimate


def test_uncertainty_estimate_rejects_invalid_bounds() -> None:
    """Enforces rejection of out-of-bounds inputs and invalid lower <= point <= upper ordering."""
    # Out of range [0, 1] inputs
    with pytest.raises(ValidationError):
        UncertaintyEstimate(
            point_estimate=1.5, lower_bound=-0.2, upper_bound=1.2, source="well_supported"
        )

    # Invalid ordering: lower_bound > point_estimate
    with pytest.raises(ValidationError):
        UncertaintyEstimate(
            point_estimate=0.4, lower_bound=0.6, upper_bound=0.8, source="well_supported"
        )

    # Invalid ordering: point_estimate > upper_bound
    with pytest.raises(ValidationError):
        UncertaintyEstimate(
            point_estimate=0.7, lower_bound=0.5, upper_bound=0.6, source="well_supported"
        )

    # Valid bounds pass correctly
    est = UncertaintyEstimate(
        point_estimate=0.5, lower_bound=0.4, upper_bound=0.6, source="well_supported"
    )
    assert est.lower_bound <= est.point_estimate <= est.upper_bound


def test_from_point_estimate_helper() -> None:
    """Consistently generates symmetric uncertainty bounds clamped to [0.0, 1.0]."""
    est = UncertaintyEstimate.from_point_estimate(0.95, source="well_supported")
    assert est.point_estimate == 0.95
    assert est.lower_bound == 0.87
    assert est.upper_bound == 1.0
    assert est.source == "well_supported"


def test_legacy_confidence_conversion() -> None:
    """Converts a legacy confidence float into an UncertaintyEstimate."""
    est = UncertaintyEstimate.from_legacy_confidence(0.85)
    assert est.point_estimate == 0.85
    assert est.lower_bound == 0.75
    assert est.upper_bound == 0.95
    assert est.source == "model_uncertainty"


def test_propagate_uncertainty_empty_input() -> None:
    """Empty input list returns conservative default estimate."""
    result = propagate_uncertainty([])
    assert result.point_estimate == 0.5
    assert result.lower_bound == 0.0
    assert result.upper_bound == 1.0
    assert result.source == "model_uncertainty"


def test_propagate_uncertainty_single_input() -> None:
    """Single input returns copy of input estimate."""
    input_est = UncertaintyEstimate.from_point_estimate(0.9, source="well_supported")
    result = propagate_uncertainty([input_est])
    assert result.point_estimate == 0.9
    assert result.source == "well_supported"


def test_propagate_uncertainty_agreeing_evidence() -> None:
    """Agreeing evidence combines into a well_supported estimate."""
    e1 = UncertaintyEstimate.from_point_estimate(0.9, source="well_supported")
    e2 = UncertaintyEstimate.from_point_estimate(0.85, source="well_supported")

    result = propagate_uncertainty([e1, e2])
    assert result.source == "well_supported"
    assert result.lower_bound <= result.point_estimate <= result.upper_bound
    assert result.lower_bound <= min(e1.lower_bound, e2.lower_bound)
    assert result.upper_bound >= max(e1.upper_bound, e2.upper_bound)


def test_propagate_uncertainty_never_narrows_on_conflict() -> None:
    """INVARIANT: Combined uncertainty MUST NEVER narrow interval on conflict."""
    e1 = UncertaintyEstimate.from_point_estimate(0.9, source="well_supported")
    e2 = UncertaintyEstimate.from_point_estimate(0.2, source="data_sparsity")

    result = propagate_uncertainty([e1, e2])

    assert result.source == "evidence_conflict"
    # Combined lower bound must be <= minimum input lower bound
    assert result.lower_bound <= min(e1.lower_bound, e2.lower_bound)
    # Combined upper bound must be >= maximum input upper bound
    assert result.upper_bound >= max(e1.upper_bound, e2.upper_bound)
    # Combined interval width must be >= maximum input interval width
    combined_width = result.upper_bound - result.lower_bound
    input_max_width = max(e1.upper_bound - e1.lower_bound, e2.upper_bound - e2.lower_bound)
    assert combined_width >= input_max_width


@pytest.mark.asyncio
async def test_synthesis_integration_conflicting_evidence() -> None:
    """Integration test: Synthesis with conflicting evidence reflects uncertainty."""
    ev1 = Evidence(
        source="Seismic API",
        claim="Earthquake magnitude is 6.5 in Tokyo.",
        uncertainty=UncertaintyEstimate.from_point_estimate(0.9, source="well_supported"),
    )
    ev2 = Evidence(
        source="NOAA Ocean API",
        claim="No seismic anomaly recorded in Tokyo region.",
        uncertainty=UncertaintyEstimate.from_point_estimate(0.2, source="data_sparsity"),
    )

    outputs = [
        AgentOutput(agent_name="seismic", evidence=[ev1]),
        AgentOutput(agent_name="ocean", evidence=[ev2]),
    ]

    synthesis_result = await synthesize(outputs)

    assert len(synthesis_result.claims) > 0
    first_claim = synthesis_result.claims[0]

    assert first_claim.uncertainty.source in (
        "evidence_conflict",
        "well_supported",
        "model_uncertainty",
        "data_sparsity",
    )
    assert 0.0 <= first_claim.confidence <= 1.0


@pytest.mark.asyncio
async def test_backward_compatibility_legacy_confidence_pipeline() -> None:
    """Verifies legacy callers using confidence=float work seamlessly end-to-end."""
    # 1. Instantiate Evidence with legacy scalar confidence float
    legacy_ev = Evidence(
        source="Legacy Station API",
        claim="PM2.5 level is 15.0 ug/m3.",
        confidence=0.88,
    )

    # 2. Verify automatic conversion to UncertaintyEstimate
    assert isinstance(legacy_ev.uncertainty, UncertaintyEstimate)
    assert legacy_ev.uncertainty.point_estimate == 0.88
    assert legacy_ev.uncertainty.source == "model_uncertainty"

    # 3. Verify .confidence compatibility property returns point_estimate
    assert legacy_ev.confidence == 0.88

    # 4. Run full synthesis pipeline with legacy evidence
    outputs = [AgentOutput(agent_name="air_quality", evidence=[legacy_ev])]
    synthesis_output = await synthesize(outputs)

    assert len(synthesis_output.claims) > 0
    synthesized_claim = synthesis_output.claims[0]

    # 5. Verify claim contains valid UncertaintyEstimate and .confidence property
    assert isinstance(synthesized_claim.uncertainty, UncertaintyEstimate)
    assert synthesized_claim.confidence == synthesized_claim.uncertainty.point_estimate
    assert 0.0 <= synthesized_claim.confidence <= 1.0
