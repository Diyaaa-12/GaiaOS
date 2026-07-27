"""Admin-only endpoint for aggregated observability metrics — Phase 3 Milestone 9.

Endpoint
--------
    GET /api/v1/admin/metrics?window=7d&group_by=complexity_tier

Access
------
    Requires Role.ADMIN. Non-admin requests receive 403.

See docs/phase3/observability.md for what is and is not tracked.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.dependencies import DbSessionDep
from auth.dependencies import RequireRole
from auth.roles import Role
from metrics.aggregation import GroupBy, MetricRollup, aggregate_metrics
from workers.scaling_policy import get_scaling_metrics

admin_metrics_router = APIRouter(prefix="/admin", tags=["Admin"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class MetricRollupSchema(BaseModel):
    """Serialised form of a MetricRollup for API consumers."""

    group_key: str | None
    count: int
    p50_latency_ms: float
    p95_latency_ms: float
    avg_cost_estimate: float
    success_rate: float

    model_config = {"from_attributes": True}


class MetricsResponse(BaseModel):
    """Container for metrics rollups and advisory worker pool scaling metrics."""

    window: str
    group_by: str
    rollups: list[MetricRollupSchema]
    queue_depth: int
    worker_utilization_pct: float
    recommended_pool_size: int


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@admin_metrics_router.get(
    "/metrics",
    response_model=MetricsResponse,
    summary="Aggregated observability metrics",
    description=(
        "Returns aggregated p50/p95 latency, success rate, cost estimate "
        "rollups, and advisory worker scaling recommendations (queue_depth, "
        "worker_utilization_pct, recommended_pool_size) for the requested window. "
        "Requires ADMIN role."
    ),
)
async def get_admin_metrics(
    session: DbSessionDep,
    window: Literal["1d", "7d", "30d", "90d"] = "7d",
    group_by: GroupBy = GroupBy.COMPLEXITY_TIER,
    _admin: object = Depends(RequireRole(Role.ADMIN)),
) -> MetricsResponse:
    """Return aggregated metric rollups and worker scaling status for given window."""
    rollups: list[MetricRollup] = await aggregate_metrics(
        session=session,
        window=window,
        group_by=group_by,
    )
    scaling_data = get_scaling_metrics()

    return MetricsResponse(
        window=window,
        group_by=group_by,
        rollups=[MetricRollupSchema(**r.__dict__) for r in rollups],
        queue_depth=scaling_data["current_queue_depth"],
        worker_utilization_pct=scaling_data["worker_utilization_pct"],
        recommended_pool_size=scaling_data["recommended_pool_size"],
    )


__all__ = ["admin_metrics_router"]
