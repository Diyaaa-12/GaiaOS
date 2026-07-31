"""SQLAlchemy model for installed agent plugins telemetry table."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class InstalledPluginRow(Base):
    """Observability table recording installed agent plugins at worker startup.

    NOTE: Python entry points remain the sole authoritative source of truth for plugin loading.
    This database table exists strictly for operational visibility and admin dashboard telemetry.
    """

    __tablename__ = "installed_plugins"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    domain: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    manifest_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    installed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
