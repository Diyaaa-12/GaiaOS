"""Health endpoints — liveness and readiness probes.

Milestone 9 — Production-style health checks.

Routes
------
GET /api/v1/health/live
    Liveness probe.  Answers only: "Is the process alive?"
    Never queries the database.  Always returns 200 while the process runs.

GET /api/v1/health/ready
    Readiness probe.  Verifies the application can actually serve traffic:
      • Database connection succeeds.
      • PostGIS extension is present.
      • pgvector (vector) extension is present.
    Returns 200 on full success; 503 when any dependency fails.

Design decisions
----------------
- ``verify_extensions()`` is imported directly from ``db.session`` — the same
  helper used by ``app.main._run_startup_db_checks()`` — so there is exactly
  one place in the codebase that knows which SQL to run for extension checks.
- ``schema_version`` is read from the ``alembic_version`` table at request
  time rather than being hardcoded.  This reflects the live migration state of
  the database rather than what the code *expects* to be applied.
- Structured logging follows the Milestone 8 pattern (``get_logger(__name__)``
  with keyword-argument fields).  Request-level logging is already handled by
  the gateway middleware; only readiness *failures* are logged here to avoid
  duplication.
- No stack traces are exposed in error responses; only a safe, human-readable
  ``reason`` string is returned.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app import __version__
from cache.client import get_redis
from db.session import get_db_session, verify_extensions
from logging_config import get_logger

_log = get_logger(__name__)

health_router = APIRouter(prefix="/health", tags=["health"])

# ---------------------------------------------------------------------------
# Dependency aliases — mirror the patterns in app.dependencies but stay local
# so health.py has no import from app.dependencies that could create cycles.
# ---------------------------------------------------------------------------
_DbSession = Annotated[AsyncSession, Depends(get_db_session)]
_Redis = Annotated[Redis, Depends(get_redis)]


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class LivenessResponse(BaseModel):
    """Response body for GET /api/v1/health/live."""

    status: str
    app_version: str
    schema_version: str


class ReadinessResponse(BaseModel):
    """Response body for GET /api/v1/health/ready (success path)."""

    status: str
    app_version: str
    schema_version: str
    database: str
    redis: str


class ReadinessFailureResponse(BaseModel):
    """Response body for GET /api/v1/health/ready (failure path, HTTP 503)."""

    status: str
    reason: str
    failing_dependency: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _get_schema_version(session: AsyncSession) -> str:
    """Return the current Alembic head revision, or 'unknown' if unavailable.

    Reads from the ``alembic_version`` table which Alembic manages.  Returns
    the string ``"unknown"`` if the table does not exist or is empty so that
    liveness is never broken by an uninitialised database.
    """
    try:
        result = await session.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
        row = result.scalar_one_or_none()
        return row if row is not None else "unknown"
    except SQLAlchemyError:
        return "unknown"


# ---------------------------------------------------------------------------
# Liveness endpoint
# ---------------------------------------------------------------------------


@health_router.get(
    "/live",
    response_model=LivenessResponse,
    summary="Liveness probe",
    description=(
        "Answers only: 'Is the process alive?'  "
        "Does NOT query the database or check any dependency.  "
        "Always returns HTTP 200 while the application process is running."
    ),
    status_code=200,
)
async def liveness() -> LivenessResponse:
    """Return 200 as long as the process is alive.

    Does not touch the database.  ``schema_version`` is ``\"unknown\"``
    because the liveness probe must never fail due to a database problem.
    """
    return LivenessResponse(
        status="alive",
        app_version=__version__,
        schema_version="unknown",
    )


# ---------------------------------------------------------------------------
# Readiness endpoint
# ---------------------------------------------------------------------------


@health_router.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="Readiness probe",
    description=(
        "Verifies the application is ready to receive traffic.  "
        "Checks database connectivity, PostGIS, pgvector, and Redis liveness.  "
        "Returns HTTP 200 on success; HTTP 503 when any dependency fails."
    ),
    status_code=200,
    responses={
        503: {
            "model": ReadinessFailureResponse,
            "description": "One or more dependencies are unavailable.",
        }
    },
)
async def readiness(db: _DbSession, redis: _Redis) -> ReadinessResponse:
    """Verify all required dependencies before accepting traffic.

    Checks performed (in order):
    1. Database connection — covered implicitly by any successful SQL call.
    2. PostGIS extension present in ``pg_extension``.
    3. pgvector (``vector``) extension present in ``pg_extension``.
    4. Redis liveness — ping check.
    5. Current Alembic schema version from ``alembic_version``.

    On any failure the handler raises HTTP 503 with a safe ``reason`` string
    and the name of the first failing dependency.  Stack traces are never
    exposed.
    """
    # --- Database connectivity + extension presence ---
    try:
        ext_status: dict[str, bool] = await verify_extensions(db)
    except SQLAlchemyError as exc:
        _log.error(
            "health.ready.db_connection_failed",
            error=str(exc),
            failing_dependency="database",
        )
        raise HTTPException(
            status_code=503,
            detail=ReadinessFailureResponse(
                status="not_ready",
                reason="Database connection failed.",
                failing_dependency="database",
            ).model_dump(),
        ) from exc

    # --- PostGIS check ---
    if not ext_status.get("postgis", False):
        _log.error(
            "health.ready.extension_missing",
            extension="postgis",
            failing_dependency="postgis",
        )
        raise HTTPException(
            status_code=503,
            detail=ReadinessFailureResponse(
                status="not_ready",
                reason="Required PostgreSQL extension 'postgis' is not installed.",
                failing_dependency="postgis",
            ).model_dump(),
        )

    # --- pgvector check ---
    if not ext_status.get("vector", False):
        _log.error(
            "health.ready.extension_missing",
            extension="vector",
            failing_dependency="pgvector",
        )
        raise HTTPException(
            status_code=503,
            detail=ReadinessFailureResponse(
                status="not_ready",
                reason="Required PostgreSQL extension 'vector' (pgvector) is not installed.",
                failing_dependency="pgvector",
            ).model_dump(),
        )

    # --- Redis liveness check ---
    try:
        await redis.ping()
    except Exception as exc:
        _log.error(
            "health.ready.redis_connection_failed",
            error=str(exc),
            failing_dependency="redis",
        )
        raise HTTPException(
            status_code=503,
            detail=ReadinessFailureResponse(
                status="not_ready",
                reason="Redis connection failed.",
                failing_dependency="redis",
            ).model_dump(),
        ) from exc

    # --- Schema version (best-effort; does not fail readiness) ---
    schema_ver = await _get_schema_version(db)

    return ReadinessResponse(
        status="ready",
        app_version=__version__,
        schema_version=schema_ver,
        database="ok",
        redis="ok",
    )


__all__ = ["health_router"]
