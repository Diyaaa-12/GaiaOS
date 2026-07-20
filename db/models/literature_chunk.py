"""SQLAlchemy ORM model for literature chunks."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Text
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column

from config.settings import get_settings
from db.base import Base

settings = get_settings()


class LiteratureChunk(Base):
    """SQLAlchemy model representing a chunk of environmental scientific literature."""

    __tablename__ = "literature_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    document_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(settings.embedding_dimension),
        nullable=True,
    )
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # extra_metadata attribute avoids conflict with reserved Base.metadata
    extra_metadata: Mapped[dict | None] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
    )

    # Computed column for full-text search
    ts_content: Mapped[str | None] = mapped_column(
        TSVECTOR,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
