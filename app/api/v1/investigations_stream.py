"""Routes for streaming investigation progress events via SSE."""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse

from app.dependencies import DbSessionDep, RedisDep
from cache.client import subscribe
from db.repository import InvestigationRepository
from logging_config import get_logger

_log = get_logger(__name__)

stream_router = APIRouter(prefix="/investigations", tags=["Investigations"])


async def sse_event_generator(investigation_id: uuid.UUID) -> AsyncIterator[str]:
    """Subscribe to Redis events and yield formatted Server-Sent Events (SSE)."""
    start_time = time.perf_counter()
    _log.info("sse.subscribe", investigation_id=str(investigation_id))
    try:
        async for event in subscribe(investigation_id):
            # Formats the event to match the client-facing SSE format
            data_json = event.data.model_dump_json()
            yield f"event: {event.event}\ndata: {data_json}\n\n"
    except Exception as exc:
        _log.error(
            "sse.stream_error",
            investigation_id=str(investigation_id),
            error=str(exc),
        )
    finally:
        duration = time.perf_counter() - start_time
        _log.info(
            "sse.unsubscribe",
            investigation_id=str(investigation_id),
            duration_connected_s=duration,
        )


@stream_router.get(
    "/{investigation_id}/stream",
    responses={
        404: {"description": "Investigation not found"},
        503: {"description": "Redis pub/sub service unavailable"},
    },
)
async def stream_investigation_events(
    investigation_id: uuid.UUID,
    db_session: DbSessionDep,
    redis_client: RedisDep,
) -> Any:
    """Stream live node-by-node execution progress of an investigation via SSE."""
    # 1. Validate if the investigation exists
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

    # 2. Check if Redis is reachable
    try:
        await redis_client.ping()
    except Exception:
        _log.error("sse.redis_unreachable", investigation_id=str(investigation_id))
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Events streaming backend is currently unreachable.",
                "error_code": "checkpointer_unavailable",
            },
        )

    # 3. Return the event stream
    return StreamingResponse(
        sse_event_generator(investigation_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
