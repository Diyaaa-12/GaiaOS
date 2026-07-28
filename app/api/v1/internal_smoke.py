"""Internal CI smoke-job endpoint for deployment integrity verification."""

from __future__ import annotations

import uuid
from typing import Any

import redis
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from rq import Queue, Retry  # type: ignore[import-untyped,import-not-found]

from app.dependencies import DbSessionDep, SettingsDep
from db.repository import InvestigationRepository
from logging_config import get_logger
from workers.jobs.investigation_job import run_investigation_job

_log = get_logger(__name__)

internal_smoke_router = APIRouter(
    prefix="/internal", tags=["Internal Infrastructure"], include_in_schema=False
)


class SmokeJobResponse(BaseModel):
    """Response returned upon enqueuing a deployment smoke test job."""

    job_id: uuid.UUID
    status: str


@internal_smoke_router.post(
    "/smoke-job",
    response_model=SmokeJobResponse,
    status_code=202,
    summary="Enqueue CI worker/scheduler deployment smoke job",
    description=(
        "Internal test endpoint used by CI to verify that background worker "
        "containers are correctly built, configured, and capable of executing jobs. "
        "Strictly gated: returns HTTP 404 in production environment."
    ),
)
async def create_smoke_job(
    settings: SettingsDep,
    db_session: DbSessionDep,
) -> Any:
    """Gated non-production endpoint that enqueues a real investigation smoke job."""
    # 1. Environment Safety Gate
    if settings.gaiaos_env.lower().strip() == "prod":
        _log.warning("internal.smoke_job.blocked_in_prod")
        raise HTTPException(status_code=404, detail="Not Found")

    # 2. Reuse production Investigation creation
    investigation = await InvestigationRepository.create_investigation(
        session=db_session,
        query="CI_DEPLOYMENT_SMOKE_TEST",
    )

    # 3. Enqueue existing production investigation job
    redis_url = settings.redis_url or "redis://localhost:6379/0"
    conn = redis.Redis.from_url(redis_url)
    queue = Queue("default", connection=conn)

    job = queue.enqueue(
        run_investigation_job,
        str(investigation.id),
        "CI_DEPLOYMENT_SMOKE_TEST",
        job_timeout=settings.job_timeout_seconds,
        retry=Retry(max=1),
    )

    _log.info(
        "internal.smoke_job.enqueued",
        investigation_id=str(investigation.id),
        job_id=job.id,
    )

    return SmokeJobResponse(
        job_id=investigation.id,
        status="enqueued",
    )
