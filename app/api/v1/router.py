"""API v1 route definitions.

This module contains the routes that are available under /api/v1.
New v1 routes should be added here (or in a separate module that is
included into ``v1_router`` from ``app.api.v1.__init__``).
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.v1.health import health_router
from app.api.v1.investigations import investigations_router
from app.api.v1.investigations_stream import stream_router
from app.dependencies import SettingsDep

v1_router = APIRouter(tags=["v1"])
v1_router.include_router(health_router)
v1_router.include_router(investigations_router)
v1_router.include_router(stream_router)


class PingResponse(BaseModel):
    """Response schema for the ping endpoint."""

    ping: str
    env: str


@v1_router.get(
    "/ping",
    response_model=PingResponse,
    summary="Liveness ping",
    description=(
        "Confirms the application is running and returns the active environment. "
        "This is a lightweight check — it does not verify database connectivity. "
        "See /api/v1/health/ready (Milestone 9) for a full dependency check."
    ),
)
def ping(settings: SettingsDep) -> PingResponse:
    """Return a simple pong with the active environment name."""
    return PingResponse(ping="pong", env=settings.gaiaos_env)


__all__ = ["v1_router"]
