"""SQLAlchemy ORM model for scaling telemetry samples (Phase 7 Audit Exit Fix)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class ScalingTelemetrySampleRow(Base):
    """ORM model for periodic RQ worker pool scaling telemetry samples.

    Stores queue depth, worker utilization, active/busy worker counts, and advisory pool
    size recommendations for historical trend analysis and M5 scaling trigger validation.
    Sampled periodically by worker scaling jobs; pruned automatically past retention window.
    """

    __tablename__ = "scaling_telemetry_samples"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    queue_depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    worker_utilization_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    active_worker_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    busy_worker_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    recommended_pool_size: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        default=lambda: datetime.now(UTC),
    )


__all__ = ["ScalingTelemetrySampleRow"]
