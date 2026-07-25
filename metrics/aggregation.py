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

    ``DOMAIN_AGENT`` is intentionally absent: no per-agent metric events are
    emitted in the current implementation. It will be added as a dimension
    when agent-level events are wired into the domain agent nodes.
    See docs/phase3/observability.md.
    """

    COMPLEXITY_TIER = "complexity_tier"
    DAY = "day"


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
    GROUP BY DATE_TRUNC('day', ts AT TIME ZONE 'UTC')
    ORDER BY DATE_TRUNC('day', ts AT TIME ZONE 'UTC') ASC
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
        Aggregation dimension. ``GroupBy.COMPLEXITY_TIER`` groups investigation
        jobs by tier (``group_key`` column, set from graph final state).
        ``GroupBy.DAY`` groups all events by calendar day (UTC).

    Returns
    -------
    list[MetricRollup]
        Empty list if no rows exist in the requested window — this is a valid
        state (e.g. freshly deployed system) and must not raise an error.
    """
    interval = _WINDOW_INTERVAL[window]  # always a literal — KeyError impossible
    # (FastAPI validates window as Literal["1d","7d","30d","90d"] before calling here)

    if group_by is GroupBy.DAY:
        sql = _SQL_GROUP_BY_DAY

    else:
        # COMPLEXITY_TIER groups on the group_key column.
        sql = _SQL_GROUP_BY_KEY

    result = await session.execute(sql, {"interval": interval})
    rows = result.fetchall()
    return [_row_to_rollup(row) for row in rows]


__all__ = ["GroupBy", "MetricRollup", "aggregate_metrics"]
