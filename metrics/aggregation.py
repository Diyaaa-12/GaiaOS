"""Metrics aggregation layer — Phase 3 Milestone 9.

Computes percentile latency, success rate, and cost rollups from raw rows
in the ``metrics`` table. All queries use parameterised expressions; no
user-supplied string is ever interpolated into SQL.

Public interface
----------------
    aggregate_metrics(session, window, group_by) -> list[MetricRollup]

Data flow
---------
    GET /admin/metrics
        -> aggregate_metrics(window="7d", group_by=GroupBy.COMPLEXITY_TIER)
        -> SELECT ... FROM metrics WHERE ts > now() - '7 days' GROUP BY group_key
        -> list[MetricRollup]
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

WindowLiteral = Literal["1d", "7d", "30d", "90d"]

_WINDOW_INTERVAL: dict[str, timedelta] = {
    "1d": timedelta(days=1),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
    "90d": timedelta(days=90),
}


class GroupBy(StrEnum):
    """Safe enumeration of supported group_by dimensions.

    Values map to fixed SQL expressions via GROUP_BY_SQL below; no user string
    is ever interpolated into a query.

    Notes
    -----
    ``COMPLEXITY_TIER`` groups investigation jobs by the tier assigned during
    graph execution ("trivial" | "moderate" | "complex"). Rows where
    ``group_key`` is NULL are investigations that did not complete tier
    classification (e.g. early failure before the supervisor ran).

    ``DAY`` groups all event types by calendar day (UTC).

    ``EVENT_TYPE`` groups rows by event_type ("JobCompleted" | "IngestionCompleted" | ...).
    """

    COMPLEXITY_TIER = "complexity_tier"
    DAY = "day"
    EVENT_TYPE = "event_type"


SUPPORTED_EVENT_TYPES: set[str] = {
    "JobCompleted",
    "JobFailed",
    "IngestionCompleted",
    "BackupCompleted",
    "RestoreDrillCompleted",
    "RestoreDrillFailed",
    "CalibrationCompleted",
    "PlannerRegionHintMissing",
    "LocationRegexFallbackExecuted",
}


@dataclass(frozen=True)
class MetricRollup:
    """Aggregated metric summary for one group_key within the requested window."""

    group_key: str | None
    count: int
    p50_latency_ms: float
    p95_latency_ms: float
    avg_cost_estimate: float
    success_rate: float


# ---------------------------------------------------------------------------
# Internal SQL templates — parameterised, never string-interpolated
# ---------------------------------------------------------------------------

# group_by=complexity_tier: group rows by the group_key column.
_SQL_GROUP_BY_KEY = text("""
    SELECT
        group_key,
        COUNT(*)                                                AS count,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY duration_ms) AS p50_latency_ms,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) AS p95_latency_ms,
        AVG(cost_estimate)                                      AS avg_cost_estimate,
        AVG(CASE WHEN success THEN 1.0 ELSE 0.0 END)           AS success_rate
    FROM metrics
    WHERE ts > now() - CAST(:interval AS INTERVAL)
      AND (CAST(:event_type AS VARCHAR) IS NULL OR event_type = CAST(:event_type AS VARCHAR))
    GROUP BY group_key
    ORDER BY count DESC
""")

# group_by=day: group rows by calendar day (UTC) using date_trunc.
_SQL_GROUP_BY_DAY = text("""
    SELECT
        TO_CHAR(DATE_TRUNC('day', ts AT TIME ZONE 'UTC'), 'YYYY-MM-DD') AS group_key,
        COUNT(*)                                                AS count,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY duration_ms) AS p50_latency_ms,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) AS p95_latency_ms,
        AVG(cost_estimate)                                      AS avg_cost_estimate,
        AVG(CASE WHEN success THEN 1.0 ELSE 0.0 END)           AS success_rate
    FROM metrics
    WHERE ts > now() - CAST(:interval AS INTERVAL)
      AND (CAST(:event_type AS VARCHAR) IS NULL OR event_type = CAST(:event_type AS VARCHAR))
    GROUP BY DATE_TRUNC('day', ts AT TIME ZONE 'UTC')
    ORDER BY DATE_TRUNC('day', ts AT TIME ZONE 'UTC') ASC
""")

# group_by=event_type: group rows by the event_type column.
_SQL_GROUP_BY_EVENT_TYPE = text("""
    SELECT
        event_type                                              AS group_key,
        COUNT(*)                                                AS count,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY duration_ms) AS p50_latency_ms,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) AS p95_latency_ms,
        AVG(cost_estimate)                                      AS avg_cost_estimate,
        AVG(CASE WHEN success THEN 1.0 ELSE 0.0 END)           AS success_rate
    FROM metrics
    WHERE ts > now() - CAST(:interval AS INTERVAL)
      AND (CAST(:event_type AS VARCHAR) IS NULL OR event_type = CAST(:event_type AS VARCHAR))
    GROUP BY event_type
    ORDER BY count DESC
""")



def _row_to_rollup(row: Any) -> MetricRollup:
    """Convert a raw SQLAlchemy result row to a MetricRollup dataclass."""
    return MetricRollup(
        group_key=row.group_key,
        count=int(row.count),
        p50_latency_ms=float(row.p50_latency_ms or 0.0),
        p95_latency_ms=float(row.p95_latency_ms or 0.0),
        avg_cost_estimate=float(row.avg_cost_estimate or 0.0),
        success_rate=float(row.success_rate or 0.0),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def aggregate_metrics(
    session: AsyncSession,
    window: WindowLiteral,
    group_by: GroupBy,
    event_type: str | None = None,
) -> list[MetricRollup]:
    """Return aggregated metric rollups for the given time window and dimension.

    Parameters
    ----------
    session:
        Async SQLAlchemy session (read-only — no writes performed here).
    window:
        Time window to aggregate over. Must be one of ``"1d"``, ``"7d"``,
        ``"30d"``, ``"90d"``. Validated by FastAPI at the endpoint layer.
    group_by:
        Aggregation dimension: ``GroupBy.COMPLEXITY_TIER``, ``GroupBy.DAY``,
        or ``GroupBy.EVENT_TYPE``.
    event_type:
        Optional event_type filter (e.g. ``"JobCompleted"``, ``"IngestionCompleted"``).
        Must be a member of ``SUPPORTED_EVENT_TYPES`` if provided.

    Returns
    -------
    list[MetricRollup]
        Empty list if no rows exist in the requested window.
    """
    if event_type is not None and event_type not in SUPPORTED_EVENT_TYPES:
        raise ValueError(
            f"Unsupported event_type {event_type!r}. Must be one of {sorted(SUPPORTED_EVENT_TYPES)}"
        )

    interval = _WINDOW_INTERVAL[window]

    if group_by is GroupBy.DAY:
        sql = _SQL_GROUP_BY_DAY
    elif group_by is GroupBy.EVENT_TYPE:
        sql = _SQL_GROUP_BY_EVENT_TYPE
    else:
        sql = _SQL_GROUP_BY_KEY

    result = await session.execute(sql, {"interval": interval, "event_type": event_type})
    rows = result.fetchall()
    return [_row_to_rollup(row) for row in rows]


__all__ = ["GroupBy", "MetricRollup", "SUPPORTED_EVENT_TYPES", "aggregate_metrics"]

