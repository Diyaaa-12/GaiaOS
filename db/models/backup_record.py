"""Database models for backup metadata and restore drill records."""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, Enum, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class BackupStatus(enum.StrEnum):
    """Lifecycle state machine for backups and restore drills."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class BackupRecord(Base):
    """Immutable audit record of a database backup attempt."""

    __tablename__ = "backup_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    backup_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[BackupStatus] = mapped_column(
        Enum(BackupStatus, name="backup_status_enum", create_type=False),
        nullable=False,
        default=BackupStatus.PENDING,
        index=True,
    )
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    storage_location: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    postgres_version: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    duration_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    verification_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    error_details: Mapped[str | None] = mapped_column(Text, nullable=True)


class RestoreDrillRecord(Base):
    """Immutable audit record of an automated restore drill execution."""

    __tablename__ = "restore_drill_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    drill_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    # backup_id is stored as a plain string without a Foreign Key constraint so that
    # historical restore drill verification records persist even after old BackupRecords are pruned.
    backup_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[BackupStatus] = mapped_column(
        Enum(BackupStatus, name="backup_status_enum", create_type=False),
        nullable=False,
        default=BackupStatus.PENDING,
        index=True,
    )
    duration_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    row_counts_match: Mapped[bool] = mapped_column(nullable=False, default=False)
    checksum_match: Mapped[bool] = mapped_column(nullable=False, default=False)
    migration_version_match: Mapped[bool] = mapped_column(nullable=False, default=False)
    discrepancies: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    error_details: Mapped[str | None] = mapped_column(Text, nullable=True)
