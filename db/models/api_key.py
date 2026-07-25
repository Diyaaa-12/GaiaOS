"""ApiKey ORM Model — Phase 3 Milestone 10."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base

if TYPE_CHECKING:
    from db.models.user import User


class ApiKey(Base):
    """ORM table for API keys issued to external consumers.

    Security model:
    - The raw API key (`gaios_live_...`) is shown ONLY ONCE at creation.
    - Only `key_hash` (SHA-256 digest) is stored in the database.
    - `key_id` (`gaios_key_...`) is a non-sensitive public identifier used
      for management API endpoints and audit logging.
    """

    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    key_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
    )
    key_hash: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    is_revoked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    owner: Mapped[User] = relationship(
        "User",
        back_populates="api_keys",
    )


__all__ = ["ApiKey"]
