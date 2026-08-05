"""Domain metric events for GaiaOS execution pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class MetricEvent:
    """Base class for all telemetry and metric events."""

    def as_dict(self) -> dict[str, Any]:
        """Convert event dataclass to dictionary with ISO formatted timestamps."""
        data = asdict(self)
        for key, val in data.items():
            if isinstance(val, datetime):
                data[key] = val.isoformat()
        return data


@dataclass
class JobStarted(MetricEvent):
    """Emitted when an RQ worker picks up and starts executing an investigation job."""

    investigation_id: str
    enqueued_at: datetime | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class JobCompleted(MetricEvent):
    """Emitted when an investigation job completes successfully."""

    investigation_id: str
    status: str
    duration_seconds: float
    llm_cost_estimate: float = 0.0
    # Set from the graph's final state; used as group_key in the metrics table
    # to support group_by=complexity_tier aggregation.
    complexity_tier: str | None = None


@dataclass
class JobFailed(MetricEvent):
    """Emitted when an investigation job fails after retries or unhandled exception."""

    investigation_id: str
    error_code: str
    error_message: str
    attempt_number: int = 1


@dataclass
class IngestionCompleted(MetricEvent):
    """Emitted when a scheduled ingestion job completes (successfully or partially)."""

    source: str
    records_fetched: int
    records_inserted: int
    duration_ms: int
    success: bool = True


@dataclass
class BackupCompleted(MetricEvent):
    """Emitted when a scheduled or manual database backup completes."""

    backup_id: str
    size_bytes: int
    duration_ms: float
    success: bool = True


@dataclass
class RestoreDrillCompleted(MetricEvent):
    """Emitted when an automated restore drill completes successfully."""

    drill_id: str
    backup_id: str
    duration_ms: float
    success: bool = True


@dataclass
class RestoreDrillFailed(MetricEvent):
    """Emitted immediately when an automated restore drill fails or detects a discrepancy."""

    drill_id: str
    backup_id: str
    duration_ms: float
    error_message: str
    discrepancies: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Phase 6 Milestone 1 — Resilience Layer metric events
# ---------------------------------------------------------------------------


@dataclass
class CircuitStateChanged(MetricEvent):
    """Emitted when a source circuit breaker transitions between states.

    Covers all three transitions:
      closed → open (threshold exceeded)
      open → half-open (timeout elapsed, probe allowed)
      half-open → closed (probe success) or half-open → open (probe failure)
    """

    source: str
    previous_state: str
    new_state: str


@dataclass
class CacheHit(MetricEvent):
    """Emitted when a resilient_call returns a cached response instead of a live one."""

    source: str
    cache_key: str
    degraded: bool = True


@dataclass
class DegradedResponseEmitted(MetricEvent):
    """Emitted when a domain agent receives a degraded (cached or unavailable) result.

    ``source_status`` is one of ``"cached"`` | ``"unavailable"``.
    """

    source: str
    source_status: str


@dataclass
class CalibrationCompleted(MetricEvent):
    """Emitted when a simulation model calibration finishes."""

    model_name: str
    promoted: bool
    version: int
    validation_score: float

