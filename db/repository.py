"""Database repository functions for managing user investigations."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.investigation import Investigation


class InvestigationRepository:
    """Helper repository to manage CRUD operations for investigations."""

    @staticmethod
    async def create_investigation(
        session: AsyncSession,
        query: str,
    ) -> Investigation:
        """Create a new investigation in the 'planning' status."""
        investigation = Investigation(
            query_text=query,
            status="planning",
        )
        session.add(investigation)
        try:
            await session.commit()
        except Exception as exc:
            await session.rollback()
            raise exc
        await session.refresh(investigation)
        return investigation

    @staticmethod
    async def update_investigation_status(
        session: AsyncSession,
        investigation_id: uuid.UUID,
        status: str,
        complexity_tier: str | None = None,
        answer: str | None = None,
        confidence: float | None = None,
        execution_trace: dict[str, Any] | None = None,
    ) -> Investigation | None:
        """Update fields of an investigation, setting completed_at if entering terminal status."""
        investigation = await InvestigationRepository.get_investigation(session, investigation_id)
        if not investigation:
            return None

        investigation.status = status
        if complexity_tier is not None:
            investigation.complexity_tier = complexity_tier
        if answer is not None:
            investigation.answer = answer
        if confidence is not None:
            investigation.confidence = confidence
        if execution_trace is not None:
            investigation.execution_trace = execution_trace

        if status in ("complete", "failed"):
            investigation.completed_at = datetime.now(UTC)

        try:
            await session.commit()
        except Exception as exc:
            await session.rollback()
            raise exc
        await session.refresh(investigation)
        return investigation

    @staticmethod
    async def get_investigation(
        session: AsyncSession,
        investigation_id: uuid.UUID,
    ) -> Investigation | None:
        """Retrieve an investigation by its primary key ID."""
        stmt = select(Investigation).where(Investigation.id == investigation_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
