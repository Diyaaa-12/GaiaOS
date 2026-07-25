"""SQLAlchemy ORM model for tracking historical hazard event ingestion cursors."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class IngestionCursor(Base):
    """SQLAlchemy model representing an ingestion cursor for a hazard data source."""

    __tablename__ = "ingestion_cursors"

    source: Mapped[str] = mapped_column(String, primary_key=True)  # e.g., "usgs", "noaa"
    last_ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
