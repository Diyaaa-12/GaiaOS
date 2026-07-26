"""PasswordResetToken ORM Model — Phase 4 Milestone 2."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base

if TYPE_CHECKING:
    from db.models.user import User


class PasswordResetToken(Base):
    """ORM table for password reset tokens issued to users.

    Security model:
    - The raw reset token (URL-safe secret) is delivered to the user via email.
    - Only `hashed_token` (SHA-256 digest) is stored in the database.
    - Single-use: `used_at` timestamp is set upon token consumption or password change.
    - Time-bound: `expires_at` timestamp limits token validity window (default 15 minutes).
    """

    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    hashed_token: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        index=True,
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    user: Mapped[User] = relationship(
        "User",
        back_populates="password_reset_tokens",
    )


__all__ = ["PasswordResetToken"]
