"""Alerting rules data structures and default system rule definitions — Phase 4 Milestone 3."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

SUPPORTED_METRICS: set[str] = {
    "investigation.p95_latency_ms",
    "investigation.job_failure_rate",
    "job_failure_rate",
    "investigation.avg_cost_estimate",
}


class AlertRuleSchema(BaseModel):
    """Pydantic schema for creating or updating an alert rule."""

    name: str = Field(..., min_length=1, max_length=255)
    metric: str = Field(..., min_length=1, max_length=255)
    threshold: float
    comparison: Literal["gt", "lt"] = "gt"
    window: Literal["15m", "1h", "1d"] = "15m"
    severity: Literal["warning", "critical"] = "warning"
    consecutive_cycles: int = Field(default=1, ge=1)
    is_enabled: bool = True

    @field_validator("metric")
    @classmethod
    def validate_metric(cls, v: str) -> str:
        if v not in SUPPORTED_METRICS:
            supported = ", ".join(sorted(SUPPORTED_METRICS))
            raise ValueError(f"Metric '{v}' is not supported. Supported metrics: {supported}")
        return v


class AlertFiring(BaseModel):
    """Container representing an active threshold violation (firing alert)."""

    rule_name: str
    metric: str
    current_value: float
    threshold: float
    comparison: str
    severity: str
    fired_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AlertResolution(BaseModel):
    """Container representing a cleared alert condition (resolved alert)."""

    rule_name: str
    metric: str
    severity: str
    resolved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# Conservative default system rules seeded during first evaluation cycle on fresh DB.
DEFAULT_ALERT_RULES: list[dict[str, float | str | int | bool]] = [
    {
        "name": "high_p95_latency",
        "metric": "investigation.p95_latency_ms",
        "threshold": 10000.0,
        "comparison": "gt",
        "window": "15m",
        "severity": "warning",
        "consecutive_cycles": 1,
        "is_enabled": True,
    },
    {
        "name": "high_job_failure_rate",
        "metric": "investigation.job_failure_rate",
        "threshold": 0.1,
        "comparison": "gt",
        "window": "1h",
        "severity": "critical",
        "consecutive_cycles": 1,
        "is_enabled": True,
    },
]


__all__ = [
    "DEFAULT_ALERT_RULES",
    "SUPPORTED_METRICS",
    "AlertFiring",
    "AlertResolution",
    "AlertRuleSchema",
]
