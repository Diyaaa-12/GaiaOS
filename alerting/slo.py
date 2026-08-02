"""Service Level Objectives (SLO) definitions and error budget burn-rate evaluation.

Phase 5 Milestone 8.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, Field


class SLODefinition(BaseModel):
    """Pydantic schema representing a Service Level Objective definition."""

    name: str = Field(..., min_length=1, max_length=255)
    target: float = Field(..., ge=0.0, le=1.0)
    window: str = Field(default="30d")
    error_budget_burn_alert_threshold: float = Field(default=10.0, gt=0.0)
    metric: str = Field(..., min_length=1, max_length=255)
    threshold: float | None = None
    comparison: Literal["gt", "lt", "eq"] = "gt"
    description: str | None = None


class BurnRateResult(BaseModel):
    """Container representing the evaluation result of an SLO error budget burn rate."""

    current_burn_rate: float
    budget_remaining_pct: float
    alert_severity: Literal["warning", "critical"] | None = None
    insufficient_data: bool = False


def evaluate_slo_burn_rate(slo: SLODefinition, actuals: list[float]) -> BurnRateResult:
    """Evaluate error budget consumption rate for a given SLO definition and metric series.

    Math
    ----
    - Error Budget = 1.0 - slo.target (e.g., target 0.99 -> error budget = 0.01)
    - Error Rate = count(bad events) / len(actuals)
    - Burn Rate = Error Rate / Error Budget
    - Budget Remaining % = max(0.0, (1.0 - Error Rate / Error Budget) * 100.0)

    Insufficient Data
    -----------------
    If ``actuals`` is empty, returns an explicit ``insufficient_data = True`` state to prevent
    false-positive or false-negative firings on missing windows.
    """
    if not actuals:
        return BurnRateResult(
            current_burn_rate=0.0,
            budget_remaining_pct=100.0,
            alert_severity=None,
            insufficient_data=True,
        )

    total_count = len(actuals)
    if slo.threshold is not None:
        if slo.comparison == "gt":
            bad_count = sum(1 for x in actuals if x > slo.threshold)
        elif slo.comparison == "lt":
            bad_count = sum(1 for x in actuals if x < slo.threshold)
        else:
            bad_count = sum(1 for x in actuals if x == slo.threshold)
    else:
        bad_count = sum(1 for x in actuals if x > 0.0)

    error_rate = bad_count / total_count
    allowed_error_rate = round(1.0 - slo.target, 6)

    if allowed_error_rate <= 0.0:
        burn_rate = 0.0
        budget_remaining_pct = 100.0
    else:
        burn_rate = round(error_rate / allowed_error_rate, 4)
        budget_remaining_pct = max(0.0, (1.0 - (error_rate / allowed_error_rate)) * 100.0)

    alert_severity: Literal["warning", "critical"] | None = None
    if burn_rate >= slo.error_budget_burn_alert_threshold:
        alert_severity = "critical" if burn_rate >= 14.4 else "warning"

    return BurnRateResult(
        current_burn_rate=burn_rate,
        budget_remaining_pct=round(budget_remaining_pct, 2),
        alert_severity=alert_severity,
        insufficient_data=False,
    )


def load_slo_definitions(path: str | Path | None = None) -> list[SLODefinition]:
    """Load versioned SLO definitions from YAML file."""
    if path is None:
        path = Path(__file__).resolve().parent.parent / "config" / "slo_definitions.yaml"

    yaml_path = Path(path)
    if not yaml_path.is_file():
        return []

    with open(yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data or "slos" not in data:
        return []

    return [SLODefinition(**item) for item in data["slos"]]


__all__ = [
    "BurnRateResult",
    "SLODefinition",
    "evaluate_slo_burn_rate",
    "load_slo_definitions",
]
