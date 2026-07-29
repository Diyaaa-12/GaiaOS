"""Minimal metrics write-path collector."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from logging_config import get_logger
from metrics.events import (
    BackupCompleted,
    IngestionCompleted,
    JobCompleted,
    JobFailed,
    MetricEvent,
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

    if isinstance(event, JobCompleted):
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
    else:
        # Unknown event subclass — log and skip rather than fail.
        _log.warning(
            "metrics.persist.unknown_event_type",
            event_type=event.__class__.__name__,
        )
        return

    session.add(row)
