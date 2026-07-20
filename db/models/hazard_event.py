"""SQLAlchemy ORM models for hazard events and hazard relationships."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base


class HazardEvent(Base):
    """SQLAlchemy model representing a historical hazard event."""

    __tablename__ = "hazard_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    event_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    region: Mapped[str] = mapped_column(String, nullable=False, index=True)
    event_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    triggered_relationships: Mapped[list[HazardRelationship]] = relationship(
        "HazardRelationship",
        foreign_keys="[HazardRelationship.parent_id]",
        back_populates="parent_event",
        cascade="all, delete-orphan",
    )
    triggering_relationships: Mapped[list[HazardRelationship]] = relationship(
        "HazardRelationship",
        foreign_keys="[HazardRelationship.child_id]",
        back_populates="child_event",
        cascade="all, delete-orphan",
    )


class HazardRelationship(Base):
    """SQLAlchemy model representing a directed causal relationship between two hazard events."""

    __tablename__ = "hazard_relationships"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    parent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hazard_events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    child_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hazard_events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relationship_type: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    parent_event: Mapped[HazardEvent] = relationship(
        "HazardEvent",
        foreign_keys=[parent_id],
        back_populates="triggered_relationships",
    )
    child_event: Mapped[HazardEvent] = relationship(
        "HazardEvent",
        foreign_keys=[child_id],
        back_populates="triggering_relationships",
    )

    __table_args__ = (
        UniqueConstraint(
            "parent_id",
            "child_id",
            "relationship_type",
            name="uq_parent_child_rel",
        ),
    )
