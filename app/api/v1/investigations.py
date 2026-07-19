"""Routes for initiating and tracking user query investigations."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from redis.asyncio import Redis

import db.session as db_session
from app.dependencies import DbSessionDep, RedisDep
from db.repository import InvestigationRepository
from logging_config import get_logger
from orchestrator.graph.builder import build_graph
from orchestrator.graph.checkpointer import RedisCheckpointSaver

_log = get_logger(__name__)

investigations_router = APIRouter(prefix="/investigations", tags=["Investigations"])


class InvestigationCreateRequest(BaseModel):
    """Payload to create a new investigation query."""

    query: str = Field(min_length=3, max_length=2000)


class InvestigationCreateResponse(BaseModel):
    """Payload returned upon successfully queuing an investigation."""

    investigation_id: uuid.UUID
    status: Literal["accepted"]
    stream_url: str
    poll_url: str


class InvestigationStatusResponse(BaseModel):
    """Current execution state of an investigation."""

    investigation_id: uuid.UUID
    status: str
    complexity_tier: str | None
    answer: str | None
    confidence: float | None
    evidence_gaps: list[str] = Field(default_factory=list)
    execution_trace: dict | None
    created_at: datetime
    completed_at: datetime | None


class ErrorResponse(BaseModel):
    """Standardized API error message container."""

    detail: str
    error_code: str


async def run_investigation_graph(
    investigation_id: uuid.UUID,
    query: str,
    redis_client: Redis,
) -> None:
    """Invokes compiled StateGraph and updates database record with execution outcomes."""
    _log.info("investigation.graph.background_start", investigation_id=str(investigation_id))

    checkpointer = RedisCheckpointSaver(redis_client)
    graph = build_graph(checkpointer)

    state = {
        "investigation_id": investigation_id,
        "query": query,
        "complexity_tier": None,
        "agent_outputs": [],
        "final_answer": None,
    }
    config = {"configurable": {"thread_id": str(investigation_id)}}

    try:
        await graph.ainvoke(state, config=config)
        _log.info(
            "investigation.graph.background_success",
            investigation_id=str(investigation_id),
        )
    except Exception as e:
        _log.error(
            "investigation.graph.background_failed",
            investigation_id=str(investigation_id),
            error=str(e),
        )
        if db_session.AsyncSessionLocal is None:
            raise RuntimeError("Database session factory is not initialised.") from e
        async with db_session.AsyncSessionLocal() as session:
            await InvestigationRepository.update_investigation_status(
                session=session,
                investigation_id=investigation_id,
                status="failed",
                answer=None,
                execution_trace={"error": str(e)},
            )


@investigations_router.post(
    "",
    response_model=InvestigationCreateResponse,
    status_code=202,
    responses={
        503: {"model": ErrorResponse, "description": "Redis Checkpointer unavailable"},
        422: {"description": "Validation Error"},
    },
)
async def create_investigation(
    payload: InvestigationCreateRequest,
    db_session: DbSessionDep,
    redis_client: RedisDep,
    background_tasks: BackgroundTasks,
) -> Any:
    """Create an investigation and invoke the compiled LangGraph asynchronously."""
    # 1. Fail fast if Redis checkpointer is unreachable
    try:
        await redis_client.ping()
    except Exception:
        _log.error("investigation.create.checkpointer_unreachable")
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Checkpointer backend is currently unreachable.",
                "error_code": "checkpointer_unavailable",
            },
        )

    # 2. Persist placeholder investigation in DB
    investigation = await InvestigationRepository.create_investigation(
        session=db_session,
        query=payload.query,
    )

    # 3. Schedule execution as a background task
    background_tasks.add_task(
        run_investigation_graph,
        investigation.id,
        payload.query,
        redis_client,
    )

    # 4. Return links
    return InvestigationCreateResponse(
        investigation_id=investigation.id,
        status="accepted",
        stream_url=f"/api/v1/investigations/{investigation.id}/stream",
        poll_url=f"/api/v1/investigations/{investigation.id}",
    )


@investigations_router.get(
    "/{investigation_id}",
    response_model=InvestigationStatusResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Investigation not found"},
    },
)
async def get_investigation(
    investigation_id: uuid.UUID,
    db_session: DbSessionDep,
) -> Any:
    """Retrieve the status and results of an investigation."""
    investigation = await InvestigationRepository.get_investigation(
        session=db_session,
        investigation_id=investigation_id,
    )
    if not investigation:
        return JSONResponse(
            status_code=404,
            content={
                "detail": f"Investigation {investigation_id} not found.",
                "error_code": "investigation_not_found",
            },
        )

    return InvestigationStatusResponse(
        investigation_id=investigation.id,
        status=investigation.status,
        complexity_tier=investigation.complexity_tier,
        answer=investigation.answer,
        confidence=investigation.confidence,
        evidence_gaps=[],  # Empty for stubs
        execution_trace=investigation.execution_trace,
        created_at=investigation.created_at,
        completed_at=investigation.completed_at,
    )
