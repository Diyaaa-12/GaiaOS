"""Evaluation benchmark database models.

These classes map directly to the PostgreSQL schema tables
``eval_benchmark_questions`` and ``eval_benchmark_runs``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base

if TYPE_CHECKING:
    from db.models.investigation import Investigation


class EvalBenchmarkQuestion(Base):
    """SQLAlchemy model representing a curated evaluation benchmark question."""

    __tablename__ = "eval_benchmark_questions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    question_text: Mapped[str] = mapped_column(String, nullable=False)
    expected_domains: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)
    expected_complexity: Mapped[str] = mapped_column(String, nullable=False)
    reference_answer: Mapped[str] = mapped_column(String, nullable=False)
    reference_evidence: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    runs: Mapped[list[EvalBenchmarkRun]] = relationship(
        "EvalBenchmarkRun",
        back_populates="question",
        cascade="all, delete-orphan",
    )


class EvalBenchmarkRun(Base):
    """SQLAlchemy model representing an execution run of an evaluation benchmark question."""

    __tablename__ = "eval_benchmark_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    benchmark_question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("eval_benchmark_questions.id", ondelete="CASCADE"),
        nullable=False,
    )
    investigation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("investigations.id", ondelete="SET NULL"),
        nullable=True,
    )
    orchestrator_version: Mapped[str] = mapped_column(String, nullable=False)
    score: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    metrics: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    question: Mapped[EvalBenchmarkQuestion] = relationship(
        "EvalBenchmarkQuestion",
        back_populates="runs",
    )
    investigation: Mapped[Investigation | None] = relationship(
        "Investigation",
        back_populates="benchmark_runs",
    )

    __table_args__ = (Index("ix_eval_runs_version", "orchestrator_version", run_at.desc()),)
