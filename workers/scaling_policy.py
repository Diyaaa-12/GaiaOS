"""Worker scaling policy and resource calculation — Phase 4 Milestone 7.

This module provides a pure deterministic calculation function for advisory worker
pool sizing, queue depth inspection from RQ, worker utilization calculations, and
periodic log summary utilities.

NOTE: Scaling recommendations are advisory only. No automated scaling or infrastructure
mutations are performed.
"""

from __future__ import annotations

import math
from typing import Any

from config.settings import get_settings
from logging_config import get_logger

_log = get_logger(__name__)


MIN_AVG_JOB_DURATION_S: float = 0.1
MIN_TARGET_WAIT_S: float = 1.0
DEFAULT_AVG_JOB_DURATION_S: float = 30.0


def recommended_pool_size(
    current_queue_depth: int,
    avg_job_duration_s: float,
    target_max_wait_s: float,
) -> int:
    """Compute advisory recommended worker pool size based on queue depth and SLA wait target.

    Formula:
        capacity_required = (current_queue_depth * avg_job_duration_s) / target_max_wait_s
        recommended_pool = ceil(capacity_required)
        clamped to min_pool_size (from WORKER_POOL_SIZE config setting)

    Pure deterministic function:
    - Never returns below configured min pool size.
    - Clamps invalid/negative inputs safely:
        queue_depth = max(0, int(current_queue_depth))
        avg_duration = max(MIN_AVG_JOB_DURATION_S, float(avg_job_duration_s))
        max_wait = max(MIN_TARGET_WAIT_S, float(target_max_wait_s))
    - Zero side effects.
    """
    settings = get_settings()
    baseline_min = settings.worker_pool_size
    min_bound = max(1, baseline_min)

    # Input sanitization and clamping
    safe_queue_depth = max(0, int(current_queue_depth))
    safe_avg_duration = max(MIN_AVG_JOB_DURATION_S, float(avg_job_duration_s))
    safe_target_wait = max(MIN_TARGET_WAIT_S, float(target_max_wait_s))

    if safe_queue_depth == 0:
        return min_bound

    capacity_required = (safe_queue_depth * safe_avg_duration) / safe_target_wait
    recommendation = math.ceil(capacity_required)

    return max(min_bound, recommendation)


def get_scaling_metrics(redis_url: str | None = None) -> dict[str, Any]:
    """Inspect active RQ worker queues and compute advisory scaling metrics.

    Reads directly from existing RQ default queue. No new Redis schema created.
    """
    import redis
    from rq import Queue, Worker

    settings = get_settings()
    url = redis_url or settings.redis_url or "redis://localhost:6379/0"

    current_queue_depth = 0
    worker_utilization_pct = 0.0
    active_worker_count = 0
    busy_worker_count = 0

    try:
        conn = redis.Redis.from_url(url)
        q = Queue("default", connection=conn)
        current_queue_depth = len(q)

        workers = Worker.all(connection=conn)
        active_worker_count = len(workers)
        if active_worker_count > 0:
            busy_worker_count = sum(1 for w in workers if w.get_state() == "busy")
            worker_utilization_pct = round((busy_worker_count / active_worker_count) * 100.0, 2)
        else:
            worker_utilization_pct = 0.0
    except Exception as exc:
        _log.warning("scaling_policy.redis_inspect_failed", error=str(exc))

    avg_duration = DEFAULT_AVG_JOB_DURATION_S
    target_wait = getattr(settings, "worker_target_max_wait_s", 60.0)

    rec_pool = recommended_pool_size(
        current_queue_depth=current_queue_depth,
        avg_job_duration_s=avg_duration,
        target_max_wait_s=target_wait,
    )

    return {
        "current_queue_depth": current_queue_depth,
        "worker_utilization_pct": worker_utilization_pct,
        "recommended_pool_size": rec_pool,
        "active_worker_count": active_worker_count,
        "busy_worker_count": busy_worker_count,
        "configured_min_pool_size": settings.worker_pool_size,
    }


def emit_scaling_summary_log(
    source: str | None = None,
    metrics: dict[str, Any] | None = None,
) -> None:
    """Emit periodic advisory scaling summary to structured logger."""
    data = metrics or get_scaling_metrics()
    _log.info(
        "scaling.summary",
        source=source or "scaling_summary",
        current_pool_size=data["configured_min_pool_size"],
        queue_depth=data["current_queue_depth"],
        worker_utilization_pct=data["worker_utilization_pct"],
        recommended_pool_size=data["recommended_pool_size"],
    )


async def record_scaling_telemetry_sample(
    session: Any,
    metrics: dict[str, Any] | None = None,
) -> Any:
    """Record a point-in-time scaling telemetry sample into the database.

    Persists queue depth, worker utilization, active worker counts, and advisory
    pool recommendation to scaling_telemetry_samples for historical trend analysis.
    """
    from db.models.scaling_telemetry import ScalingTelemetrySampleRow

    data = metrics or get_scaling_metrics()
    sample = ScalingTelemetrySampleRow(
        queue_depth=data["current_queue_depth"],
        worker_utilization_pct=data["worker_utilization_pct"],
        active_worker_count=data["active_worker_count"],
        busy_worker_count=data["busy_worker_count"],
        recommended_pool_size=data["recommended_pool_size"],
    )
    session.add(sample)
    await session.commit()
    return sample


async def prune_scaling_telemetry_samples(
    session: Any,
    retention_days: int = 30,
) -> int:
    """Delete scaling telemetry samples older than retention_days.

    Maintains a bounded table footprint in PostgreSQL.
    """
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import delete

    from db.models.scaling_telemetry import ScalingTelemetrySampleRow

    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    stmt = delete(ScalingTelemetrySampleRow).where(ScalingTelemetrySampleRow.ts < cutoff)
    result = await session.execute(stmt)
    await session.commit()
    return int(result.rowcount or 0)


async def get_historical_scaling_telemetry(
    session: Any,
    window: str = "7d",
    queue_depth_threshold: int = 20,
    queue_depth_sustained_seconds: float = 900.0,
    utilization_threshold: float = 100.0,
    utilization_sustained_seconds: float = 600.0,
) -> dict[str, Any]:
    """Query historical scaling telemetry summary and evaluate M5 sustained trigger criteria.

    Windows: "1d", "7d", "30d", "90d".
    Evaluates:
    - Peak & average queue depth
    - Peak & average worker utilization %
    - Transient vs sustained trigger evaluation:
      - Threshold crossed at least once: max_queue_depth > 20 OR max_worker_utilization_pct >= 100%
      - Sustained queue depth breach: queue_depth > 20 sustained for >= 15 min (900s)
      - Sustained utilization breach: worker_utilization_pct >= 100% sustained for >= 10 min (600s)
    """
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import func, select

    from db.models.scaling_telemetry import ScalingTelemetrySampleRow

    days_map = {"1d": 1, "7d": 7, "30d": 30, "90d": 90}
    days = days_map.get(window, 7)
    cutoff = datetime.now(UTC) - timedelta(days=days)

    stmt = select(
        func.count(ScalingTelemetrySampleRow.id).label("sample_count"),
        func.max(ScalingTelemetrySampleRow.queue_depth).label("max_queue_depth"),
        func.avg(ScalingTelemetrySampleRow.queue_depth).label("avg_queue_depth"),
        func.max(ScalingTelemetrySampleRow.worker_utilization_pct).label(
            "max_worker_utilization_pct"
        ),
        func.avg(ScalingTelemetrySampleRow.worker_utilization_pct).label(
            "avg_worker_utilization_pct"
        ),
    ).where(ScalingTelemetrySampleRow.ts >= cutoff)

    res = (await session.execute(stmt)).first()

    sample_count = res.sample_count if res and res.sample_count else 0
    max_queue_depth = res.max_queue_depth if res and res.max_queue_depth is not None else 0
    avg_queue_depth = (
        float(res.avg_queue_depth) if res and res.avg_queue_depth is not None else 0.0
    )
    max_worker_utilization_pct = (
        float(res.max_worker_utilization_pct)
        if res and res.max_worker_utilization_pct is not None
        else 0.0
    )
    avg_worker_utilization_pct = (
        float(res.avg_worker_utilization_pct)
        if res and res.avg_worker_utilization_pct is not None
        else 0.0
    )

    threshold_crossed = (max_queue_depth > queue_depth_threshold) or (
        max_worker_utilization_pct >= utilization_threshold
    )

    stmt_samples = (
        select(ScalingTelemetrySampleRow)
        .where(ScalingTelemetrySampleRow.ts >= cutoff)
        .order_by(ScalingTelemetrySampleRow.ts.asc())
    )
    samples = (await session.execute(stmt_samples)).scalars().all()

    settings = get_settings()
    sampling_interval = float(getattr(settings, "scaling_summary_interval_s", 300.0))
    max_gap_seconds = max(600.0, 2.0 * sampling_interval)

    sustained_queue_depth_breach = False
    qd_start: datetime | None = None
    qd_last: datetime | None = None

    for s in samples:
        if s.queue_depth > queue_depth_threshold:
            if qd_start is None:
                qd_start = s.ts
            elif qd_last is not None and (s.ts - qd_last).total_seconds() > max_gap_seconds:
                qd_start = s.ts

            if qd_start is not None and (
                (s.ts - qd_start).total_seconds() >= queue_depth_sustained_seconds
            ):
                sustained_queue_depth_breach = True
                break

            qd_last = s.ts
        else:
            qd_start = None
            qd_last = None

    sustained_utilization_breach = False
    util_start: datetime | None = None
    util_last: datetime | None = None

    for s in samples:
        if s.worker_utilization_pct >= utilization_threshold:
            if util_start is None:
                util_start = s.ts
            elif util_last is not None and (s.ts - util_last).total_seconds() > max_gap_seconds:
                util_start = s.ts

            if util_start is not None and (
                (s.ts - util_start).total_seconds() >= utilization_sustained_seconds
            ):
                sustained_utilization_breach = True
                break

            util_last = s.ts
        else:
            util_start = None
            util_last = None

    sustained_trigger_satisfied = (
        sustained_queue_depth_breach or sustained_utilization_breach
    )

    if sustained_trigger_satisfied:
        scaling_verdict = (
            "Outcome A — Multi-Node Scaling Triggered (Sustained Threshold Met)"
        )
    elif threshold_crossed:
        scaling_verdict = (
            "Outcome B — Multi-Node Scaling Deferred "
            "(Transient Spike Only, Sustained Duration Not Met)"
        )
    else:
        scaling_verdict = (
            "Outcome B — Multi-Node Scaling Deferred (Threshold Never Crossed)"
        )

    return {
        "window": window,
        "sample_count": sample_count,
        "max_queue_depth": max_queue_depth,
        "avg_queue_depth": round(avg_queue_depth, 2),
        "max_worker_utilization_pct": round(max_worker_utilization_pct, 2),
        "avg_worker_utilization_pct": round(avg_worker_utilization_pct, 2),
        "threshold_crossed_at_least_once": threshold_crossed,
        "sustained_queue_depth_breach": sustained_queue_depth_breach,
        "sustained_utilization_breach": sustained_utilization_breach,
        "sustained_trigger_satisfied": sustained_trigger_satisfied,
        "triggers_met": sustained_trigger_satisfied,
        "scaling_verdict": scaling_verdict,
    }


__all__ = [
    "MIN_AVG_JOB_DURATION_S",
    "MIN_TARGET_WAIT_S",
    "DEFAULT_AVG_JOB_DURATION_S",
    "recommended_pool_size",
    "get_scaling_metrics",
    "emit_scaling_summary_log",
    "record_scaling_telemetry_sample",
    "prune_scaling_telemetry_samples",
    "get_historical_scaling_telemetry",
]
