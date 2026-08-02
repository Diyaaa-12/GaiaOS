"""Unit tests for SLO definitions and error budget burn-rate evaluation — Phase 5 Milestone 8."""

from __future__ import annotations

from alerting.slo import (
    SLODefinition,
    evaluate_slo_burn_rate,
    load_slo_definitions,
)


def test_slo_definition_pydantic_validation() -> None:
    """Verify SLODefinition schema validation."""
    slo = SLODefinition(
        name="test_slo",
        target=0.99,
        window="30d",
        error_budget_burn_alert_threshold=10.0,
        metric="job_success_rate",
        threshold=0.99,
        comparison="lt",
    )
    assert slo.name == "test_slo"
    assert slo.target == 0.99
    assert slo.error_budget_burn_alert_threshold == 10.0


def test_evaluate_slo_burn_rate_zero_errors() -> None:
    """Synthetic time series with 0 errors yields 0.0 burn rate and 100% budget."""
    slo = SLODefinition(
        name="job_success_rate",
        target=0.99,
        window="30d",
        error_budget_burn_alert_threshold=10.0,
        metric="job_success_rate",
        threshold=0.99,
        comparison="lt",
    )

    actuals = [1.0] * 100
    res = evaluate_slo_burn_rate(slo, actuals)

    assert res.insufficient_data is False
    assert res.current_burn_rate == 0.0
    assert res.budget_remaining_pct == 100.0
    assert res.alert_severity is None


def test_evaluate_slo_burn_rate_sustainable_consumption() -> None:
    """Synthetic time series at allowable error rate yields burn_rate = 1.0."""
    slo = SLODefinition(
        name="job_success_rate",
        target=0.99,
        window="30d",
        error_budget_burn_alert_threshold=10.0,
        metric="job_success_rate",
        threshold=0.99,
        comparison="lt",
    )

    actuals = [1.0] * 99 + [0.0]
    res = evaluate_slo_burn_rate(slo, actuals)

    assert res.insufficient_data is False
    assert res.current_burn_rate == 1.0
    assert res.budget_remaining_pct == 0.0
    assert res.alert_severity is None


def test_evaluate_slo_burn_rate_exceeds_threshold_fires_alert() -> None:
    """Synthetic time series burning budget 10x faster fires warning/critical alert."""
    slo = SLODefinition(
        name="job_success_rate",
        target=0.99,
        window="30d",
        error_budget_burn_alert_threshold=10.0,
        metric="job_success_rate",
        threshold=0.99,
        comparison="lt",
    )

    actuals = [1.0] * 90 + [0.0] * 10
    res = evaluate_slo_burn_rate(slo, actuals)

    assert res.insufficient_data is False
    assert res.current_burn_rate == 10.0
    assert res.budget_remaining_pct == 0.0
    assert res.alert_severity == "warning"


def test_evaluate_slo_burn_rate_latency_gt_threshold() -> None:
    """Latency SLO with gt comparison evaluating durations against threshold."""
    slo = SLODefinition(
        name="investigation_p95_latency",
        target=0.95,
        window="30d",
        error_budget_burn_alert_threshold=10.0,
        metric="investigation.p95_latency_ms",
        threshold=10000.0,
        comparison="gt",
    )

    actuals = [500.0] * 98 + [12000.0] * 2
    res = evaluate_slo_burn_rate(slo, actuals)

    assert res.insufficient_data is False
    assert res.current_burn_rate == 0.4
    assert res.budget_remaining_pct == 60.0
    assert res.alert_severity is None


def test_evaluate_slo_burn_rate_insufficient_data() -> None:
    """Empty actuals list must return explicit insufficient_data state."""
    slo = SLODefinition(
        name="job_success_rate",
        target=0.99,
        window="30d",
        error_budget_burn_alert_threshold=10.0,
        metric="job_success_rate",
    )

    res = evaluate_slo_burn_rate(slo, [])
    assert res.insufficient_data is True
    assert res.current_burn_rate == 0.0
    assert res.budget_remaining_pct == 100.0
    assert res.alert_severity is None


def test_load_slo_definitions_from_yaml() -> None:
    """Verify loading slo_definitions.yaml contains expected SLO definitions."""
    slos = load_slo_definitions()
    assert len(slos) == 4
    names = {slo.name for slo in slos}
    assert "investigation_p95_latency" in names
    assert "job_success_rate" in names
    assert "calibration_ece" in names
    assert "citation_fallback_rate" in names
