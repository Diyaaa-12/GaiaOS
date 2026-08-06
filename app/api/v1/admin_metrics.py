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

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from app.dependencies import DbReadSessionDep
from auth.dependencies import RequireRole, get_current_active_user, get_current_user
from auth.roles import Role
from config.settings import get_settings
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
    session: DbReadSessionDep,
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


async def verify_prometheus_auth(
    request: Request,
) -> None:
    """Verify authorization for Prometheus metrics scraping.

    Supports long-lived scrapers via static PROMETHEUS_METRICS_TOKEN header,
    or falls back to standard ADMIN user JWT / API key authentication.
    """
    settings = get_settings()
    if settings.prometheus_metrics_token:
        auth_header = request.headers.get("Authorization", "")
        custom_header = request.headers.get("X-Prometheus-Token", "")
        token = ""
        if auth_header.startswith("Bearer "):
            token = auth_header.split("Bearer ")[1].strip()
        elif auth_header.startswith("Token "):
            token = auth_header.split("Token ")[1].strip()
        elif custom_header:
            token = custom_header.strip()

        if token and token == settings.prometheus_metrics_token:
            return

    user = await get_current_active_user(await get_current_user(request))
    role_checker = RequireRole(Role.ADMIN)
    await role_checker(user=user)


@admin_metrics_router.get(
    "/metrics/prometheus",
    summary="Prometheus / OpenMetrics exposition endpoint",
    description=(
        "Returns system telemetry, worker scaling gauges, and location fallback "
        "counters formatted in standard OpenMetrics text format. Authenticates via "
        "static PROMETHEUS_METRICS_TOKEN or ADMIN role."
    ),
)
async def get_prometheus_metrics(
    _auth: None = Depends(verify_prometheus_auth),
) -> Response:
    """Return system telemetry formatted for Prometheus scraping.

    Note on Maintenance Cost:
    GaiaOS uses zero-dependency custom MetricCounter instances to avoid third-party
    prometheus_client lock-in. Any future MetricCounter added to metrics/collector.py
    must be manually registered in this function to appear in OpenMetrics output.
    """
    from metrics.collector import (
        LOCATION_REGEX_FALLBACK_TOTAL,
        PLANNER_REGION_HINT_MISSING_TOTAL,
    )

    scaling_data = get_scaling_metrics()
    agents = ["seismic", "ocean", "atmosphere", "air_quality", "wildfire"]

    lines = [
        "# HELP gaiaos_planner_region_hint_missing_total Missing region_hint before fallback count",
        "# TYPE gaiaos_planner_region_hint_missing_total counter",
    ]
    for agent in agents:
        val = PLANNER_REGION_HINT_MISSING_TOTAL.get(agent=agent)
        lines.append(f'gaiaos_planner_region_hint_missing_total{{agent="{agent}"}} {val}')

    lines.extend(
        [
            "# HELP gaiaos_location_regex_fallback_total Location regex fallback execution count",
            "# TYPE gaiaos_location_regex_fallback_total counter",
        ]
    )
    for agent in agents:
        val = LOCATION_REGEX_FALLBACK_TOTAL.get(agent=agent)
        lines.append(f'gaiaos_location_regex_fallback_total{{agent="{agent}"}} {val}')

    lines.extend(
        [
            "# HELP gaiaos_queue_depth Current RQ task queue depth",
            "# TYPE gaiaos_queue_depth gauge",
            f"gaiaos_queue_depth {scaling_data['current_queue_depth']}",
            "# HELP gaiaos_worker_utilization_pct Current worker utilization percentage",
            "# TYPE gaiaos_worker_utilization_pct gauge",
            f"gaiaos_worker_utilization_pct {scaling_data['worker_utilization_pct']}",
            "# HELP gaiaos_recommended_pool_size Recommended RQ worker pool size",
            "# TYPE gaiaos_recommended_pool_size gauge",
            f"gaiaos_recommended_pool_size {scaling_data['recommended_pool_size']}",
            "",
        ]
    )

    return Response(
        content="\n".join(lines),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


__all__ = ["admin_metrics_router"]
