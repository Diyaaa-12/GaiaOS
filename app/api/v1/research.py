"""Public Research API endpoints — Phase 5 Milestone 9.

Read-only, SLO-backed, versioned public API exposing aggregated, anonymized
investigation findings and the causal-chain hazard dataset.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select

from app.api.v1.anonymization import AnonymizationPolicy
from app.dependencies import DbSessionDep
from config.settings import get_settings
from db.models.hazard_event import HazardEvent
from db.repository import InvestigationRepository
from logging_config import get_logger

_log = get_logger(__name__)

research_router = APIRouter(prefix="/research", tags=["Public Research"])


class ResearchInvestigationResponse(BaseModel):
    """Anonymized investigation schema returned to public research consumers."""

    investigation_id: uuid.UUID
    query_category: str
    domains_involved: list[str]
    complexity_tier: str | None
    confidence_summary: float | None
    consent_public_research: bool
    query_text: str | None = None
    execution_trace: dict[str, Any] | None = None
    created_at: datetime
    completed_at: datetime | None = None


class HazardEventResponse(BaseModel):
    """Public hazard event schema."""

    id: uuid.UUID
    event_type: str
    region_label: str | None
    event_date: datetime
    details: str | None
    source: str | None
    external_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ErrorResponse(BaseModel):
    """Standardized API error message container."""

    detail: str
    error_code: str


@research_router.get(
    "/investigations",
    response_model=list[ResearchInvestigationResponse],
    summary="List anonymized public research findings",
    description=(
        "Returns aggregated, anonymized investigation findings. "
        "User identity (user_id) is strictly omitted (ADR-504). "
        "Raw query text is included ONLY if the submitter provided explicit consent."
    ),
    responses={503: {"model": ErrorResponse, "description": "Public research API disabled"}},
)
async def list_public_research_investigations(
    session: DbSessionDep,
    domain: str | None = Query(
        default=None, description="Filter by domain (e.g., seismic)"
    ),
    since: datetime | None = Query(
        default=None, description="Filter investigations since timestamp"
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> Any:
    """List paginated, anonymized public research investigations."""
    settings = get_settings()
    if not settings.public_research_api_enabled:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "detail": "Public Research API is disabled by feature flag.",
                "error_code": "public_research_api_disabled",
            },
        )

    investigations = await InvestigationRepository.list_research_investigations(
        session=session,
        domain=domain,
        since=since,
        limit=limit,
        offset=offset,
    )

    anonymized_results = [AnonymizationPolicy.apply(inv) for inv in investigations]
    _log.info(
        "research.api.investigations_queried",
        count=len(anonymized_results),
        domain=domain,
    )
    return anonymized_results


@research_router.get(
    "/hazard-events",
    response_model=list[HazardEventResponse],
    summary="List public hazard events",
    description="Returns historical hazard events from public data sources (USGS, NOAA, FIRMS).",
    responses={503: {"model": ErrorResponse, "description": "Public research API disabled"}},
)
async def list_public_hazard_events(
    session: DbSessionDep,
    event_type: str | None = Query(
        default=None, description="Filter by event type (e.g., earthquake)"
    ),
    source: str | None = Query(default=None, description="Filter by source (e.g., USGS)"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> Any:
    """List paginated public hazard events."""
    settings = get_settings()
    if not settings.public_research_api_enabled:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "detail": "Public Research API is disabled by feature flag.",
                "error_code": "public_research_api_disabled",
            },
        )

    stmt = select(HazardEvent)
    if event_type:
        stmt = stmt.where(HazardEvent.event_type == event_type)
    if source:
        stmt = stmt.where(HazardEvent.source == source)

    stmt = stmt.order_by(HazardEvent.event_date.desc()).limit(limit).offset(offset)
    res = await session.execute(stmt)
    events = list(res.scalars().all())

    _log.info(
        "research.api.hazard_events_queried",
        count=len(events),
        event_type=event_type,
    )
    return events


__all__ = ["research_router"]
