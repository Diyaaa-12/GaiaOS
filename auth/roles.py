"""Role definitions for GaiaOS access control."""

from enum import StrEnum


class Role(StrEnum):
    """User roles per Architecture v1.0 §3.6."""

    USER = "user"
    RESEARCHER = "researcher"
    ADMIN = "admin"
