"""API package.

Exports the top-level ``api_router`` that is mounted in ``app.main``
under the ``/api`` prefix.  All versioned sub-routers are included here.
"""

from fastapi import APIRouter

from app.api.v1 import v1_router

api_router = APIRouter()
api_router.include_router(v1_router, prefix="/v1")

__all__ = ["api_router"]
