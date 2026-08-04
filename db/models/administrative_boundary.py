"""SQLAlchemy ORM model for OpenStreetMap administrative boundaries."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class AdministrativeBoundary(Base):
    """SQLAlchemy model representing an OpenStreetMap administrative boundary polygon."""

    __tablename__ = "administrative_boundaries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    osm_id: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    admin_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    geom: Mapped[Any] = mapped_column(
        Geometry(geometry_type="MULTIPOLYGON", srid=4326),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
