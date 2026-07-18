"""Dependency providers for FastAPI's Depends() system.

This module is the single extension point for all injectable resources.
Route handlers should import from here, never directly from config or db.

Adding a new resource means adding a new provider function here — existing
routes remain untouched.
"""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import Settings
from config.settings import get_settings as _get_settings
from db.session import get_db_session as _get_db_session


def get_settings() -> Settings:
    """Return the application settings.

    Delegates to the lru_cache-backed factory in config.settings so the
    Settings object is constructed exactly once per process lifetime.
    """
    return _get_settings()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session for the duration of a request.

    The session is opened and closed by ``db.session.get_db_session``.
    Callers must call ``session.commit()`` or ``session.rollback()``
    explicitly; this provider only guarantees cleanup.

    Raises ``RuntimeError`` if the database engine has not been initialised
    (i.e. the application is not fully started).
    """
    async for session in _get_db_session():
        yield session


# ---------------------------------------------------------------------------
# Convenience type aliases
# Routes annotate parameters with these instead of the verbose Depends form.
# ---------------------------------------------------------------------------

# Injected application settings.
SettingsDep = Annotated[Settings, Depends(get_settings)]

# Injected async DB session — scoped to the current request.
DbSessionDep = Annotated[AsyncSession, Depends(get_db_session)]
