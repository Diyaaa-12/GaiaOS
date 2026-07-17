"""Dependency providers for FastAPI's Depends() system.

This module is the single extension point for all injectable resources.
Route handlers should import from here, never directly from config or db.

Adding a new resource (e.g. a DB session in Milestone 5) means adding a
new provider function here — existing routes remain untouched.
"""

from typing import Annotated

from fastapi import Depends

from config.settings import Settings
from config.settings import get_settings as _get_settings


def get_settings() -> Settings:
    """Return the application settings.

    Delegates to the lru_cache-backed factory in config.settings so the
    Settings object is constructed exactly once per process lifetime.
    """
    return _get_settings()


# Convenience type alias — routes use `SettingsDep` as a type annotation
# to keep signatures short and readable.
SettingsDep = Annotated[Settings, Depends(get_settings)]
