"""Admin-only endpoints for managing alert rules and incident history — Phase 4 Milestone 3.

Endpoints
---------
    GET /api/v1/admin/alerts?status=firing
    GET /api/v1/admin/alert-rules
    POST /api/v1/admin/alert-rules
    DELETE /api/v1/admin/alert-rules/{rule_id}

Access
------
    Requires Role.ADMIN. Non-admin requests receive 403 Forbidden.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from alerting.rules import AlertRuleSchema
from app.dependencies import DbSessionDep
from auth.dependencies import RequireRole
from auth.roles import Role
from db.repository import AlertRepository

admin_alerts_router = APIRouter(prefix="/admin", tags=["Admin Alerts"])


# ---------------------------------------------------------------------------
# Response & Request schemas
# ---------------------------------------------------------------------------


class AlertRuleResponse(BaseModel):
    """API response model for an alert rule."""

    id: uuid.UUID
    name: str
    metric: str
    threshold: float
    comparison: str
    window: str
    severity: str
    consecutive_cycles: int
    is_enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AlertIncidentResponse(BaseModel):
    """API response model for an alert incident."""

    id: uuid.UUID
    rule_id: uuid.UUID | None
    rule_name: str
    severity: str
    status: str
    last_value: float
    threshold: float
    consecutive_violations: int
    fired_at: datetime
    resolved_at: datetime | None

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    """Standardized response container."""

    message: str
    status: str = "success"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@admin_alerts_router.get(
    "/alerts",
    response_model=list[AlertIncidentResponse],
    summary="List alert incidents",
    description="Returns current and historical alert incidents. Requires ADMIN role.",
)
async def list_alert_incidents(
    session: DbSessionDep,
    status_filter: Literal["firing", "resolved"] | None = Query(
        default=None, alias="status", description="Filter by incident status"
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _admin: object = Depends(RequireRole(Role.ADMIN)),
) -> Any:
    """List alert incidents with optional status filter."""
    incidents = await AlertRepository.list_incidents(
        session=session,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return incidents


@admin_alerts_router.get(
    "/alert-rules",
    response_model=list[AlertRuleResponse],
    summary="List configured alert rules",
    description="Returns all configured alerting rules. Requires ADMIN role.",
)
async def list_alert_rules(
    session: DbSessionDep,
    _admin: object = Depends(RequireRole(Role.ADMIN)),
) -> Any:
    """List all alert rules."""
    rules = await AlertRepository.list_alert_rules(session)
    return rules


@admin_alerts_router.post(
    "/alert-rules",
    response_model=AlertRuleResponse,
    status_code=status.HTTP_200_OK,
    summary="Create or update an alert rule (idempotent upsert)",
    description=(
        "Upserts an alert rule by name. If a rule with the name exists, "
        "updates its configuration. Requires ADMIN role."
    ),
)
async def upsert_alert_rule(
    payload: AlertRuleSchema,
    session: DbSessionDep,
    _admin: object = Depends(RequireRole(Role.ADMIN)),
) -> Any:
    """Create or update an alert rule by name."""
    rule = await AlertRepository.upsert_alert_rule(
        session=session,
        name=payload.name,
        metric=payload.metric,
        threshold=payload.threshold,
        comparison=payload.comparison,
        window=payload.window,
        severity=payload.severity,
        consecutive_cycles=payload.consecutive_cycles,
        is_enabled=payload.is_enabled,
    )
    return rule


@admin_alerts_router.delete(
    "/alert-rules/{rule_id}",
    response_model=MessageResponse,
    summary="Delete an alert rule",
    responses={404: {"description": "Alert rule not found"}},
)
async def delete_alert_rule(
    rule_id: uuid.UUID,
    session: DbSessionDep,
    _admin: object = Depends(RequireRole(Role.ADMIN)),
) -> Any:
    """Delete an alert rule by primary key ID."""
    deleted = await AlertRepository.delete_alert_rule(session, rule_id)
    if not deleted:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "detail": f"Alert rule '{rule_id}' not found.",
                "error_code": "alert_rule_not_found",
            },
        )
    return MessageResponse(
        message=f"Alert rule '{rule_id}' deleted successfully.",
        status="success",
    )


__all__ = ["admin_alerts_router"]
