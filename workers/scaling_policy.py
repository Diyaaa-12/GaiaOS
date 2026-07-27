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


__all__ = [
    "MIN_AVG_JOB_DURATION_S",
    "MIN_TARGET_WAIT_S",
    "DEFAULT_AVG_JOB_DURATION_S",
    "recommended_pool_size",
    "get_scaling_metrics",
    "emit_scaling_summary_log",
]
