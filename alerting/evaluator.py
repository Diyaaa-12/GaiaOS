"""Alerting evaluator engine — Phase 4 Milestone 3.

Evaluates configured AlertRules against metrics rollups from PostgreSQL.
Optimised to group rule evaluations by sliding time window to minimise DB queries.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from alerting.rules import SUPPORTED_METRICS, AlertFiring
from logging_config import get_logger

if TYPE_CHECKING:
    from db.models.alert_rule import AlertRule

_log = get_logger(__name__)

_WINDOW_INTERVAL: dict[str, timedelta] = {
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
    "1d": timedelta(days=1),
}

_SQL_WINDOW_SNAPSHOT = text("""
    SELECT
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) AS p95_latency_ms,
        AVG(CASE WHEN success THEN 0.0 ELSE 1.0 END)              AS job_failure_rate,
        AVG(cost_estimate)                                         AS avg_cost_estimate
    FROM metrics
    WHERE ts > now() - CAST(:interval AS INTERVAL)
""")


def _is_threshold_violated(current_value: float, threshold: float, comparison: str) -> bool:
    """Check if threshold is violated based on comparison operator."""
    if comparison == "gt":
        return current_value > threshold
    elif comparison == "lt":
        return current_value < threshold
    return False


async def _fetch_window_metrics_snapshot(session: AsyncSession, window: str) -> dict[str, float]:
    """Fetch single grouped SQL metrics snapshot for a specific sliding time window."""
    interval = _WINDOW_INTERVAL.get(window, timedelta(minutes=15))
    result = await session.execute(_SQL_WINDOW_SNAPSHOT, {"interval": interval})
    row = result.fetchone()

    snapshot: dict[str, float] = {
        "investigation.p95_latency_ms": 0.0,
        "investigation.job_failure_rate": 0.0,
        "job_failure_rate": 0.0,
        "investigation.avg_cost_estimate": 0.0,
    }

    if row:
        if row.p95_latency_ms is not None:
            snapshot["investigation.p95_latency_ms"] = float(row.p95_latency_ms)
        if row.job_failure_rate is not None:
            snapshot["investigation.job_failure_rate"] = float(row.job_failure_rate)
            snapshot["job_failure_rate"] = float(row.job_failure_rate)
        if row.avg_cost_estimate is not None:
            snapshot["investigation.avg_cost_estimate"] = float(row.avg_cost_estimate)

    return snapshot


async def evaluate_rules(
    session: AsyncSession,
    rules: list[AlertRule],
) -> list[AlertFiring]:
    """Evaluate active alert rules against metrics data grouped by sliding window.

    Optimisation: Groups rules by window so only 1 SQL query is executed per window,
    rather than 1 SQL query per rule.
    """
    firings: list[AlertFiring] = []
    now = datetime.now(UTC)

    # 1. Group active rules by window
    rules_by_window: dict[str, list[AlertRule]] = defaultdict(list)
    for rule in rules:
        if rule.is_enabled:
            rules_by_window[rule.window].append(rule)

    # 2. Evaluate each window group against a single snapshot query
    for window, window_rules in rules_by_window.items():
        try:
            snapshot = await _fetch_window_metrics_snapshot(session, window)
            for rule in window_rules:
                if rule.metric not in SUPPORTED_METRICS:
                    _log.error(
                        "alerting.evaluator.unsupported_metric",
                        rule_name=rule.name,
                        metric=rule.metric,
                    )
                    continue

                current_val = snapshot.get(rule.metric, 0.0)
                if _is_threshold_violated(current_val, rule.threshold, rule.comparison):
                    firings.append(
                        AlertFiring(
                            rule_name=rule.name,
                            metric=rule.metric,
                            current_value=current_val,
                            threshold=rule.threshold,
                            comparison=rule.comparison,
                            severity=rule.severity,
                            fired_at=now,
                        )
                    )
        except Exception as exc:
            _log.warning(
                "alerting.evaluator.window_evaluation_failed",
                window=window,
                error=str(exc),
            )

    return firings


__all__ = ["evaluate_rules"]
