"""AlertRule ORM Model — Phase 4 Milestone 3."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base

if TYPE_CHECKING:
    from db.models.alert_incident import AlertIncident


class AlertRule(Base):
    """ORM table for configurable alerting rules.

    Fields
    ------
    name:
        Unique rule name (e.g. "high_p95_latency", "investigation_job_failure_rate").
    metric:
        Metric name to evaluate (e.g. "investigation.p95_latency_ms").
    threshold:
        Numeric threshold value.
    comparison:
        "gt" (greater than) or "lt" (less than).
    window:
        Sliding time window ("15m", "1h", "1d").
    severity:
        "warning" or "critical".
    consecutive_cycles:
        Number of consecutive firing cycles required before notifying (flapping suppression).
    is_enabled:
        Boolean toggle for rule evaluation.
    """

    __tablename__ = "alert_rules"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    metric: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    threshold: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    comparison: Mapped[str] = mapped_column(
        String(10),
        default="gt",
        nullable=False,
    )
    window: Mapped[str] = mapped_column(
        String(20),
        default="15m",
        nullable=False,
    )
    severity: Mapped[str] = mapped_column(
        String(20),
        default="warning",
        nullable=False,
    )
    consecutive_cycles: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    incidents: Mapped[list[AlertIncident]] = relationship(
        "AlertIncident",
        back_populates="rule",
        cascade="all, delete-orphan",
    )


__all__ = ["AlertRule"]
