"""Periodic scaling telemetry sampling job — Phase 7 Audit Exit Fix.

Collects point-in-time RQ worker scaling metrics, records a sample in PostgreSQL
(scaling_telemetry_samples), and prunes expired samples past the retention window (30 days).
"""

from __future__ import annotations

from typing import Any

from db.session import get_async_session_context
from logging_config import get_logger
from workers.scaling_policy import (
    get_scaling_metrics,
    prune_scaling_telemetry_samples,
    record_scaling_telemetry_sample,
)

_log = get_logger(__name__)


async def _async_run_scaling_telemetry_job() -> dict[str, Any]:
    """Execute async scaling telemetry sampling and pruning run."""
    metrics = get_scaling_metrics()
    async with get_async_session_context() as session:
        sample = await record_scaling_telemetry_sample(session=session, metrics=metrics)
        pruned_count = await prune_scaling_telemetry_samples(session=session, retention_days=30)

    _log.info(
        "scaling_telemetry_job.completed",
        sample_id=str(sample.id),
        queue_depth=metrics["current_queue_depth"],
        worker_utilization_pct=metrics["worker_utilization_pct"],
        pruned_samples=pruned_count,
    )

    return {
        "status": "success",
        "sample_id": str(sample.id),
        "queue_depth": metrics["current_queue_depth"],
        "worker_utilization_pct": metrics["worker_utilization_pct"],
        "pruned_samples": pruned_count,
    }


def run_scaling_telemetry_job(source: str | None = None) -> dict[str, Any]:
    """Synchronous RQ entry-point wrapper for scaling telemetry sampling job."""
    import asyncio

    return asyncio.run(_async_run_scaling_telemetry_job())


__all__ = ["run_scaling_telemetry_job", "_async_run_scaling_telemetry_job"]
