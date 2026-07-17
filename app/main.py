"""GaiaOS FastAPI application entry point.

Responsibilities of this module (and nothing more):
- Create the FastAPI application instance with project metadata.
- Register all routers.
- Configure the lifespan context manager for startup / shutdown hooks.

Business logic, route handlers, and dependency providers each live in
their own modules (api/ and dependencies.py respectively).
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from app import __version__
from app.api import api_router
from app.api.root import root_router
from app.dependencies import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager.

    Startup logic (e.g. DB connection pool initialisation) goes in the
    section before ``yield``.  Shutdown / cleanup logic goes after.
    Both sections are intentionally empty in Milestone 4 — they will be
    populated in Milestone 5 (DB connection layer).
    """
    # --- startup ---
    settings = get_settings()
    # TODO(M8): replace with structured logger once logging layer is in place
    print(
        f"[GaiaOS] starting up | env={settings.gaiaos_env} "
        f"| log_level={settings.log_level}",
        flush=True,
    )
    yield
    # --- shutdown ---
    # TODO(M8): replace with structured logger once logging layer is in place
    print("[GaiaOS] shutting down", flush=True)


def create_app() -> FastAPI:
    """Construct and configure the FastAPI application.

    Using a factory function (rather than a module-level ``app = FastAPI()``)
    makes the app easier to instantiate in tests with different settings.
    """
    application = FastAPI(
        title="GaiaOS",
        version=__version__,
        description=(
            "An Agentic Planetary Risk Intelligence Platform. "
            "Phase 1 — foundational API skeleton."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Service-level root (outside versioned namespace)
    application.include_router(root_router)

    # Versioned API namespace — all routes live under /api/vN
    application.include_router(api_router, prefix="/api")

    return application


# Module-level instance consumed by uvicorn and by tests.
app: FastAPI = create_app()
