"""RQ Job definition for executing GaiaOS investigation graphs."""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import UTC
from typing import Any

from rq import get_current_job

import db.session as db_session
from cache.client import get_redis
from config.settings import get_settings
from db.repository import InvestigationRepository
from logging_config import configure_logging, get_logger
from metrics.collector import emit
from metrics.events import JobCompleted, JobFailed, JobStarted
from orchestrator.graph.builder import build_graph
from orchestrator.graph.checkpointer import RedisCheckpointSaver

_log = get_logger(__name__)


async def _async_run_investigation(investigation_id: uuid.UUID, query: str | None = None) -> None:
    """Async execution wrapper for running an investigation graph."""
    settings = get_settings()
    configure_logging(settings)
    if settings.database_url and db_session.AsyncSessionLocal is None:
        db_session.init_engine()

    job = get_current_job()
    enqueued_at = job.enqueued_at if job else None
    if enqueued_at and enqueued_at.tzinfo is None:
        enqueued_at = enqueued_at.replace(tzinfo=UTC)

    emit(
        JobStarted(
            investigation_id=str(investigation_id),
            enqueued_at=enqueued_at,
        )
    )

    redis_client = await get_redis()
    checkpointer = RedisCheckpointSaver(redis_client)
    graph = build_graph(checkpointer)

    # Retrieve investigation query if not explicitly passed
    if not query:
        if db_session.AsyncSessionLocal is None:
            raise RuntimeError("Database session factory is not initialised.")
        async with db_session.AsyncSessionLocal() as session:
            inv = await InvestigationRepository.get_investigation(session, investigation_id)
            if not inv:
                raise ValueError(f"Investigation {investigation_id} not found in database.")
            query = inv.query_text

    state: dict[str, Any] = {
        "investigation_id": investigation_id,
        "query": query,
        "complexity_tier": None,
        "agent_outputs": [],
        "final_answer": None,
    }
    config: Any = {"configurable": {"thread_id": str(investigation_id)}}

    start_time = time.monotonic()
    try:
        await graph.ainvoke(state, config=config)
        duration = round(time.monotonic() - start_time, 3)

        _log.info(
            "investigation.job.success",
            investigation_id=str(investigation_id),
            job_id=job.id if job else None,
            duration=duration,
        )
        emit(
            JobCompleted(
                investigation_id=str(investigation_id),
                status="complete",
                duration_seconds=duration,
            )
        )

    except Exception as exc:
        duration = round(time.monotonic() - start_time, 3)
        retries_left = getattr(job, "retries_left", 0) if job else 0
        is_terminal_failure = retries_left <= 0
        error_code = "job_retries_exhausted" if is_terminal_failure else "job_attempt_failed"
        attempt_number = max(1, 3 - retries_left) if job else 1

        _log.error(
            "investigation.job.failed",
            investigation_id=str(investigation_id),
            job_id=job.id if job else None,
            duration=duration,
            error=str(exc),
            is_terminal_failure=is_terminal_failure,
            retries_left=retries_left,
        )

        emit(
            JobFailed(
                investigation_id=str(investigation_id),
                error_code=error_code,
                error_message=str(exc),
                attempt_number=attempt_number,
            )
        )

        if is_terminal_failure and db_session.AsyncSessionLocal is not None:
            async with db_session.AsyncSessionLocal() as session:
                await InvestigationRepository.update_investigation_status(
                    session=session,
                    investigation_id=investigation_id,
                    status="failed",
                    answer=None,
                    execution_trace={"error": str(exc), "error_code": error_code},
                )

        raise exc


def run_investigation_job(investigation_id: str | uuid.UUID, query: str | None = None) -> None:
    """RQ sync entry point for executing an investigation job.

    Bridges RQ synchronous job execution to async LangGraph invocation.
    """
    if isinstance(investigation_id, str):
        inv_uuid = uuid.UUID(investigation_id)
    else:
        inv_uuid = investigation_id

    asyncio.run(_async_run_investigation(inv_uuid, query))


__all__ = ["run_investigation_job"]
