"""Root endpoint (service-level, outside the versioned /api/v1 namespace).

Provides a simple landing response so a bare GET / returns meaningful JSON
rather than a 404 or an HTML page.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app import __version__
from app.dependencies import SettingsDep

root_router = APIRouter(tags=["root"])


class RootResponse(BaseModel):
    """Response schema for the root endpoint."""

    service: str
    status: str
    version: str
    env: str


@root_router.get(
    "/",
    response_model=RootResponse,
    summary="Service root",
    description="Returns basic service identity information. Not versioned.",
)
def read_root(settings: SettingsDep) -> RootResponse:
    """Return service identity and current environment."""
    return RootResponse(
        service="GaiaOS",
        status="ok",
        version=__version__,
        env=settings.gaiaos_env,
    )


__all__ = ["root_router"]
