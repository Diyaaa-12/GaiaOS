"""SQLAlchemy ORM model for longitudinal pattern findings (Phase 7 Milestone 2)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class PatternFinding(Base):
    """SQLAlchemy model representing a versioned longitudinal pattern finding."""

    __tablename__ = "pattern_findings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    pattern_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    algorithm_version: Mapped[str] = mapped_column(String(16), nullable=False, default="1.0")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    source_event_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    target_event_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    region_label: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    time_window_days: Mapped[int] = mapped_column(Integer, nullable=False)
    support_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total_source_events: Mapped[int] = mapped_column(Integer, nullable=False)
    total_target_events: Mapped[int] = mapped_column(Integer, nullable=False)
    observed_rate: Mapped[float] = mapped_column(Float, nullable=False)
    baseline_rate: Mapped[float] = mapped_column(Float, nullable=False)
    lift: Mapped[float] = mapped_column(Float, nullable=False)
    statistical_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    uncertainty: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    supporting_event_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    mined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        Index(
            "ix_pattern_findings_active_confidence",
            "is_active",
            "statistical_confidence",
        ),
    )
