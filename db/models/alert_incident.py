"""AlertIncident ORM Model — Phase 4 Milestone 3."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base

if TYPE_CHECKING:
    from db.models.alert_rule import AlertRule


class AlertIncident(Base):
    """ORM table recording alert firings and resolutions.

    Fields
    ------
    rule_id:
        Foreign key referencing the parent AlertRule.
    rule_name:
        Denormalised rule name for fast querying and historical context.
    severity:
        "warning" or "critical".
    status:
        "firing" or "resolved".
    last_value:
        Most recent metric value observed during evaluation.
    threshold:
        Threshold value evaluated against.
    consecutive_violations:
        Count of consecutive evaluation runs this rule has violated threshold.
    fired_at:
        Timestamp when the incident initially transitioned to firing.
    resolved_at:
        Timestamp when the condition cleared and incident resolved (NULL while firing).
    """

    __tablename__ = "alert_incidents"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    rule_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("alert_rules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    rule_name: Mapped[str] = mapped_column(
        String(255),
        index=True,
        nullable=False,
    )
    slo_name: Mapped[str | None] = mapped_column(
        String(255),
        index=True,
        nullable=True,
    )
    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="firing",
        index=True,
        nullable=False,
    )
    last_value: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    threshold: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    consecutive_violations: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    fired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
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

    rule: Mapped[AlertRule | None] = relationship(
        "AlertRule",
        back_populates="incidents",
    )


__all__ = ["AlertIncident"]
