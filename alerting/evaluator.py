"""Alerting evaluator engine — Phase 4 Milestone 3 & Phase 5 Milestone 8.

Evaluates configured AlertRules and SLO definitions against metrics rollups from PostgreSQL.
Optimised to group evaluations by sliding time window to minimise DB queries.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from alerting.rules import SUPPORTED_METRICS, AlertFiring
from alerting.slo import BurnRateResult, SLODefinition, evaluate_slo_burn_rate
from logging_config import get_logger

if TYPE_CHECKING:
    from db.models.alert_rule import AlertRule

_log = get_logger(__name__)

_WINDOW_INTERVAL: dict[str, timedelta] = {
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
    "1d": timedelta(days=1),
    "30d": timedelta(days=30),
}

_SQL_WINDOW_SNAPSHOT = text("""
    SELECT
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) AS p95_latency_ms,
        AVG(CASE WHEN success THEN 0.0 ELSE 1.0 END)              AS job_failure_rate,
        AVG(cost_estimate)                                         AS avg_cost_estimate
    FROM metrics
    WHERE ts > now() - CAST(:interval AS INTERVAL)
""")

_SQL_QUEUE_WAIT_P95 = text("""
    SELECT
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY queue_wait_ms) AS p95_queue_wait_ms
    FROM metrics
    WHERE ts > now() - CAST(:interval AS INTERVAL)
      AND event_type = 'JobStarted'
      AND queue_wait_ms IS NOT NULL
""")

_SQL_TELEMETRY_SNAPSHOT = text("""
    SELECT
        queue_depth,
        worker_utilization_pct
    FROM scaling_telemetry_samples
    WHERE ts > now() - CAST(:interval AS INTERVAL)
    ORDER BY ts DESC
    LIMIT 1
""")

_SQL_METRICS_LATENCY = text("""
    SELECT duration_ms FROM metrics
    WHERE ts > now() - CAST(:interval AS INTERVAL) AND duration_ms IS NOT NULL
""")

_SQL_METRICS_SUCCESS = text("""
    SELECT CASE WHEN success THEN 1.0 ELSE 0.0 END FROM metrics
    WHERE ts > now() - CAST(:interval AS INTERVAL)
""")

_SQL_EVAL_ECE = text("""
    SELECT CAST(metrics->>'calibration_ece' AS FLOAT)
    FROM eval_benchmark_runs
    WHERE run_at > now() - CAST(:interval AS INTERVAL)
      AND metrics IS NOT NULL AND metrics->>'calibration_ece' IS NOT NULL
""")

_SQL_EVAL_FALLBACK = text("""
    SELECT CAST(metrics->>'citation_fallback_rate' AS FLOAT)
    FROM eval_benchmark_runs
    WHERE run_at > now() - CAST(:interval AS INTERVAL)
      AND metrics IS NOT NULL AND metrics->>'citation_fallback_rate' IS NOT NULL
""")


def _is_threshold_violated(current_value: float, threshold: float, comparison: str) -> bool:
    """Check if threshold is violated based on comparison operator."""
    if comparison == "gt":
        return current_value > threshold
    elif comparison == "gte":
        return current_value >= threshold
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
        "scaling.queue_depth": 0.0,
        "scaling.worker_utilization_pct": 0.0,
        "scaling.p95_queue_wait_s": 0.0,
    }

    if row:
        if row.p95_latency_ms is not None:
            snapshot["investigation.p95_latency_ms"] = float(row.p95_latency_ms)
        if row.job_failure_rate is not None:
            snapshot["investigation.job_failure_rate"] = float(row.job_failure_rate)
            snapshot["job_failure_rate"] = float(row.job_failure_rate)
        if row.avg_cost_estimate is not None:
            snapshot["investigation.avg_cost_estimate"] = float(row.avg_cost_estimate)

    try:
        qw_res = await session.execute(_SQL_QUEUE_WAIT_P95, {"interval": interval})
        qw_row = qw_res.fetchone()
        if qw_row and qw_row.p95_queue_wait_ms is not None:
            snapshot["scaling.p95_queue_wait_s"] = float(qw_row.p95_queue_wait_ms) / 1000.0
    except Exception as exc:
        _log.warning("alerting.evaluator.fetch_queue_wait_p95_failed", error=str(exc))

    try:
        telem_res = await session.execute(_SQL_TELEMETRY_SNAPSHOT, {"interval": interval})
        telem_row = telem_res.fetchone()
        if telem_row:
            if telem_row.queue_depth is not None:
                snapshot["scaling.queue_depth"] = float(telem_row.queue_depth)
            if telem_row.worker_utilization_pct is not None:
                snapshot["scaling.worker_utilization_pct"] = float(telem_row.worker_utilization_pct)
    except Exception as exc:
        _log.warning("alerting.evaluator.fetch_telemetry_snapshot_failed", error=str(exc))

    return snapshot


async def _fetch_slo_actuals(session: AsyncSession, slo: SLODefinition) -> list[float]:
    """Fetch metric actuals time series for a given SLO definition."""
    interval = _WINDOW_INTERVAL.get(slo.window, timedelta(days=30))
    try:
        if slo.metric in ("investigation.p95_latency_ms", "p95_latency"):
            res = await session.execute(_SQL_METRICS_LATENCY, {"interval": interval})
            return [float(r[0]) for r in res.fetchall() if r[0] is not None]
        elif slo.metric in ("investigation.job_success_rate", "job_success_rate"):
            res = await session.execute(_SQL_METRICS_SUCCESS, {"interval": interval})
            return [float(r[0]) for r in res.fetchall() if r[0] is not None]
        elif slo.metric == "calibration_ece":
            res = await session.execute(_SQL_EVAL_ECE, {"interval": interval})
            return [float(r[0]) for r in res.fetchall() if r[0] is not None]
        elif slo.metric == "citation_fallback_rate":
            res = await session.execute(_SQL_EVAL_FALLBACK, {"interval": interval})
            return [float(r[0]) for r in res.fetchall() if r[0] is not None]
    except Exception as exc:
        _log.warning(
            "alerting.evaluator.fetch_slo_actuals_failed",
            slo_name=slo.name,
            metric=slo.metric,
            error=str(exc),
        )
    return []


async def evaluate_rules(
    session: AsyncSession,
    rules: list[AlertRule],
) -> list[AlertFiring]:
    """Evaluate active alert rules against metrics data grouped by sliding window."""
    from config.settings import get_settings

    firings: list[AlertFiring] = []
    now = datetime.now(UTC)
    settings = get_settings()

    rules_by_window: dict[str, list[AlertRule]] = defaultdict(list)
    for rule in rules:
        if rule.is_enabled:
            rules_by_window[rule.window].append(rule)

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
                # Compute dynamic threshold for queue depth based on current WORKER_POOL_SIZE
                effective_threshold = (
                    float(10 * settings.worker_pool_size)
                    if rule.metric == "scaling.queue_depth"
                    else rule.threshold
                )

                if _is_threshold_violated(current_val, effective_threshold, rule.comparison):
                    firings.append(
                        AlertFiring(
                            rule_name=rule.name,
                            metric=rule.metric,
                            current_value=current_val,
                            threshold=effective_threshold,
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


async def evaluate_slos(
    session: AsyncSession,
    slos: list[SLODefinition],
) -> tuple[list[AlertFiring], dict[str, BurnRateResult]]:
    """Evaluate list of SLODefinitions against historical DB actuals.

    Returns
    -------
    tuple[list[AlertFiring], dict[str, BurnRateResult]]
        - AlertFirings for any SLO whose burn rate violates burn threshold
        - Dictionary mapping slo.name to its BurnRateResult (for metrics/telemetry)
    """
    firings: list[AlertFiring] = []
    burn_results: dict[str, BurnRateResult] = {}
    now = datetime.now(UTC)

    for slo in slos:
        actuals = await _fetch_slo_actuals(session, slo)
        res = evaluate_slo_burn_rate(slo, actuals)
        burn_results[slo.name] = res

        if res.insufficient_data:
            _log.info(
                "alerting.evaluator.slo_insufficient_data",
                slo_name=slo.name,
                metric=slo.metric,
                window=slo.window,
            )
            continue

        if res.alert_severity:
            firings.append(
                AlertFiring(
                    rule_name=slo.name,
                    metric=slo.metric,
                    current_value=res.current_burn_rate,
                    threshold=slo.error_budget_burn_alert_threshold,
                    comparison="gt",
                    severity=res.alert_severity,
                    slo_name=slo.name,
                    fired_at=now,
                )
            )

    return firings, burn_results


__all__ = ["evaluate_rules", "evaluate_slos"]
