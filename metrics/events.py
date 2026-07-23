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


@dataclass
class JobFailed(MetricEvent):
    """Emitted when an investigation job fails after retries or unhandled exception."""

    investigation_id: str
    error_code: str
    error_message: str
    attempt_number: int = 1
