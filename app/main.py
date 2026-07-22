"""GaiaOS FastAPI application entry point.

Responsibilities of this module (and nothing more):
- Create the FastAPI application instance with project metadata.
- Register all routers.
- Configure the lifespan context manager for startup / shutdown hooks.

Business logic, route handlers, and dependency providers each live in
their own modules (api/ and dependencies.py respectively).
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

import db.session as _db_session
from app import __version__
from app.api import api_router
from app.api.root import root_router
from app.dependencies import get_settings
from auth.jwt_provider import JWTAuthProvider
from cache import dispose_redis, init_redis
from db.session import dispose_engine, init_engine, verify_extensions
from gateway.middleware import GatewayMiddleware
from logging_config import configure_logging, get_logger

_log = get_logger(__name__)


async def _run_startup_db_checks() -> None:
    """Verify DB extensions and extension usability after engine init.

    Performs three checks required by Milestone 5 acceptance criteria:
    1. PostGIS and pgvector extensions are present (reads pg_extension).
    2. A throwaway geometry column can be created and queried.
    3. A throwaway vector column can be created and queried.

    All DDL is wrapped in a transaction that is explicitly rolled back, so
    no schema objects persist after the check.  This makes the check safe
    to run on every startup including in production.

    Raises ``RuntimeError`` if either required extension is missing.
    Raises ``sqlalchemy.exc.OperationalError`` on connection failure.
    """
    # Access through the module so we see the value set by init_engine(),
    # not the None that was bound at import time.
    if _db_session.AsyncSessionLocal is None:
        raise RuntimeError("init_engine() must be called before _run_startup_db_checks()")

    async with _db_session.AsyncSessionLocal() as session:
        # --- 1. Extension presence check ---
        ext_status = await verify_extensions(session)
        missing = [name for name, present in ext_status.items() if not present]
        if missing:
            raise RuntimeError(
                f"Required PostgreSQL extensions are not installed: {missing}.  "
                "Ensure the database was initialised with init-extensions.sql."
            )
        _log.info("db.extensions.verified", extensions=ext_status)

        # --- 2. Throwaway geometry check (PostGIS) ---
        # --- 3. Throwaway vector check (pgvector) ---
        # Both DDL blocks are run inside a savepoint that is always rolled
        # back so the throwaway tables never exist after this function returns.
        try:
            await session.execute(text("SAVEPOINT m5_check"))
            await session.execute(
                text("CREATE TEMP TABLE _m5_geom_check (geom geometry(Point, 4326))")
            )
            await session.execute(
                text("INSERT INTO _m5_geom_check VALUES (ST_GeomFromText('POINT(0 0)', 4326))")
            )
            await session.execute(text("SELECT ST_AsText(geom) FROM _m5_geom_check"))

            await session.execute(text("CREATE TEMP TABLE _m5_vec_check (embedding vector(3))"))
            await session.execute(text("INSERT INTO _m5_vec_check VALUES ('[1.0, 2.0, 3.0]')"))
            await session.execute(text("SELECT embedding FROM _m5_vec_check"))

            _log.info("db.postgis.ok")
            _log.info("db.pgvector.ok")
        finally:
            # Roll back to the savepoint so temporary tables are discarded
            # even if the checks fail partway through.
            await session.execute(text("ROLLBACK TO SAVEPOINT m5_check"))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager.

    Startup:  initialise the connection pool; run extension and extension-
              usability checks (Milestone 5 acceptance criteria).
    Shutdown: dispose the connection pool cleanly.
    """
    settings = get_settings()
    _log.info(
        "app.startup",
        env=settings.gaiaos_env,
        log_level=settings.log_level,
    )

    # --- startup ---
    init_engine()
    await _run_startup_db_checks()
    await init_redis(settings)

    yield

    # --- shutdown ---
    await dispose_redis()
    await dispose_engine()
    _log.info("app.shutdown")


def create_app() -> FastAPI:
    """Construct and configure the FastAPI application.

    Using a factory function (rather than a module-level ``app = FastAPI()``)
    makes the app easier to instantiate in tests with different settings.
    """
    settings = get_settings()

    # Logging must be configured before any logger is used, including loggers
    # obtained at module import time (e.g. in middleware).  This is the single
    # call site for logging configuration in the entire application.
    configure_logging(settings)

    application = FastAPI(
        title="GaiaOS",
        version=__version__,
        description=(
            "An Agentic Planetary Risk Intelligence Platform. Phase 1 — foundational API skeleton."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Gateway middleware — must be the last add_middleware() call so that
    # Starlette's reverse-registration order places it outermost, running
    # first on every incoming request.
    auth_provider = JWTAuthProvider() if settings.enable_auth else None
    application.add_middleware(GatewayMiddleware, auth=auth_provider)

    # Service-level root (outside versioned namespace)
    application.include_router(root_router)

    # Versioned API namespace — all routes live under /api/vN
    application.include_router(api_router, prefix="/api")

    return application


# Module-level instance consumed by uvicorn and by tests.
app: FastAPI = create_app()
