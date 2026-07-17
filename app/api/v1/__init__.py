"""API v1 package.

Exports the ``v1_router`` that collects all version-1 route modules.
Add new v1 route modules by importing their routers and including them here.
"""

from app.api.v1.router import v1_router

__all__ = ["v1_router"]
