"""Minimal metrics write-path collector."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from logging_config import get_logger
from metrics.events import (
    BackupCompleted,
    CalibrationCompleted,
    IngestionCompleted,
    JobCompleted,
    JobFailed,
    JobStarted,
    LocationRegexFallbackExecuted,
    MetricEvent,
    PlannerRegionHintMissing,
    RestoreDrillCompleted,
    RestoreDrillFailed,
)

_log = get_logger(__name__)


def emit(event: MetricEvent) -> None:
    """Emit a metric event to structured access logs.

    This is the minimal write path for Phase 3 Milestone 3.
    Full aggregation metrics backend is implemented in Milestone 9.
    """
    event_type = event.__class__.__name__
    _log.info("metrics.event", event_type=event_type, **event.as_dict())


async def persist_metric(session: AsyncSession, event: MetricEvent) -> None:
    """Persist a metric event as a raw row in the metrics table.

    Called by worker jobs after emit() to store data for aggregation.
    The session must be externally managed (commit/rollback owned by caller).

    group_key semantics:
    - JobCompleted: stores the investigation's complexity_tier (may be None)
    - JobFailed:    None (no tier available at failure time)
    - IngestionCompleted: stores the source name (e.g. "usgs", "noaa")

    avg_cost_estimate: stored from llm_cost_estimate; currently always 0.0
    until real LLM cost tracking is wired into the graph nodes.
    """
    # Import here to avoid circular imports at module level; the ORM model
    # depends on db.base which is orthogonal to metrics.events.
    from db.models.metric_event import MetricEventRow

    if isinstance(event, JobStarted):
        queue_wait_ms: int | None = None
        if event.enqueued_at is not None:
            delta_s = (event.started_at - event.enqueued_at).total_seconds()
            queue_wait_ms = max(0, int(delta_s * 1000))
        row = MetricEventRow(
            event_type="JobStarted",
            group_key=None,
            duration_ms=0,
            queue_wait_ms=queue_wait_ms,
            cost_estimate=Decimal("0"),
            success=True,
        )
    elif isinstance(event, JobCompleted):
        row = MetricEventRow(
            event_type="JobCompleted",
            group_key=event.complexity_tier,  # None when tier not yet determined
            duration_ms=int(event.duration_seconds * 1000),
            cost_estimate=Decimal(str(event.llm_cost_estimate)),
            success=True,
        )
    elif isinstance(event, JobFailed):
        row = MetricEventRow(
            event_type="JobFailed",
            group_key=None,
            duration_ms=0,
            cost_estimate=Decimal("0"),
            success=False,
        )
    elif isinstance(event, IngestionCompleted):
        row = MetricEventRow(
            event_type="IngestionCompleted",
            group_key=event.source,
            duration_ms=event.duration_ms,
            cost_estimate=Decimal("0"),
            success=event.success,
        )
    elif isinstance(event, BackupCompleted):
        row = MetricEventRow(
            event_type="BackupCompleted",
            group_key=event.backup_id,
            duration_ms=int(event.duration_ms),
            cost_estimate=Decimal("0"),
            success=event.success,
        )
    elif isinstance(event, RestoreDrillCompleted):
        row = MetricEventRow(
            event_type="RestoreDrillCompleted",
            group_key=event.drill_id,
            duration_ms=int(event.duration_ms),
            cost_estimate=Decimal("0"),
            success=event.success,
        )
    elif isinstance(event, RestoreDrillFailed):
        row = MetricEventRow(
            event_type="RestoreDrillFailed",
            group_key=event.drill_id,
            duration_ms=int(event.duration_ms),
            cost_estimate=Decimal("0"),
            success=False,
        )
    elif isinstance(event, CalibrationCompleted):
        row = MetricEventRow(
            event_type="CalibrationCompleted",
            group_key=event.model_name,
            duration_ms=0,
            cost_estimate=Decimal("0"),
            success=event.promoted,
        )
    elif isinstance(event, (PlannerRegionHintMissing, LocationRegexFallbackExecuted)):
        row = MetricEventRow(
            event_type=event.__class__.__name__,
            group_key=event.agent,
            duration_ms=0,
            cost_estimate=Decimal("0"),
            success=True,
        )
    else:
        # Unknown event subclass — log and skip rather than fail.
        _log.warning(
            "metrics.persist.unknown_event_type",
            event_type=event.__class__.__name__,
        )
        return

    session.add(row)


class MetricCounterLabel:
    def __init__(
        self, parent: MetricCounter, key: tuple[tuple[str, str], ...], labels: dict[str, str]
    ) -> None:
        self.parent = parent
        self.key = key
        self.labels = labels

    def inc(self, amount: int = 1) -> None:
        self.parent._counts[self.key] = self.parent._counts.get(self.key, 0) + amount
        agent = self.labels.get("agent", "unknown")
        if self.parent.name == "gaiaos_planner_region_hint_missing_total":
            emit(PlannerRegionHintMissing(agent=agent))
        elif self.parent.name == "gaiaos_location_regex_fallback_total":
            emit(LocationRegexFallbackExecuted(agent=agent))


class MetricCounter:
    """Lightweight metric counter supporting .labels(...).inc()."""

    def __init__(self, name: str, description: str) -> None:
        self.name: str = name
        self.description: str = description
        self._counts: dict[tuple[tuple[str, str], ...], int] = {}

    def labels(self, **label_kwargs: str) -> MetricCounterLabel:
        key = tuple(sorted(label_kwargs.items()))
        return MetricCounterLabel(self, key, label_kwargs)

    def get(self, **label_kwargs: str) -> int:
        key = tuple(sorted(label_kwargs.items()))
        return self._counts.get(key, 0)


PLANNER_REGION_HINT_MISSING_TOTAL = MetricCounter(
    "gaiaos_planner_region_hint_missing_total",
    "Count of queries missing region_hint before fallback",
)

LOCATION_REGEX_FALLBACK_TOTAL = MetricCounter(
    "gaiaos_location_regex_fallback_total",
    "Count of location extraction regex fallback executions",
)
