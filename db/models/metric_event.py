"""SQLAlchemy ORM model for the metrics table (Phase 3 Milestone 9)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class MetricEventRow(Base):
    """ORM model for a raw metric event row stored for aggregation.

    One row is inserted per emitted MetricEvent (JobCompleted, JobFailed,
    IngestionCompleted). Aggregation is performed on-demand by
    metrics.aggregation.aggregate_metrics(); rows are never mutated.
    """

    __tablename__ = "metrics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    # "JobCompleted" | "JobFailed" | "IngestionCompleted"
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    # complexity_tier for investigation jobs; source for ingestion jobs; None otherwise.
    group_key: Mapped[str | None] = mapped_column(String, nullable=True)
    # Execution duration in milliseconds.
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Queue wait latency in milliseconds (JobStarted events). Null if unmeasured.
    queue_wait_ms: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    # LLM cost in USD; 0.0 until real cost tracking is wired.
    cost_estimate: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=6), nullable=False, default=Decimal("0")
    )
    # True for success events; False for failure events.
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Event timestamp; indexed for time-window GROUP BY queries.
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
