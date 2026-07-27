"""Admin-only read-only endpoints for database backups and restore drill history."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select

from app.dependencies import DbSessionDep
from auth.dependencies import RequireRole
from auth.roles import Role
from db.models.backup_record import BackupRecord, RestoreDrillRecord

admin_backups_router = APIRouter(prefix="/admin", tags=["Admin"])


class BackupRecordSchema(BaseModel):
    """API response schema for a database backup audit record."""

    backup_id: str
    created_at: datetime
    completed_at: datetime | None
    status: str
    size_bytes: int
    checksum: str
    storage_location: str
    postgres_version: str
    duration_ms: float
    verification_metadata: dict[str, Any]
    error_details: str | None

    model_config = {"from_attributes": True}


class RestoreDrillRecordSchema(BaseModel):
    """API response schema for a restore drill audit record."""

    drill_id: str
    backup_id: str
    started_at: datetime
    completed_at: datetime | None
    status: str
    duration_ms: float
    row_counts_match: bool
    checksum_match: bool
    migration_version_match: bool
    discrepancies: dict[str, Any]
    error_details: str | None

    model_config = {"from_attributes": True}


@admin_backups_router.get(
    "/backups",
    response_model=list[BackupRecordSchema],
    summary="List database backup history",
    description=(
        "Returns read-only history of automated and manual database backup executions. "
        "Requires ADMIN role."
    ),
)
async def list_backups(
    session: DbSessionDep,
    limit: int = Query(default=50, ge=1, le=200),
    _admin: object = Depends(RequireRole(Role.ADMIN)),
) -> list[BackupRecordSchema]:
    """Return historical database backup records."""
    stmt = select(BackupRecord).order_by(BackupRecord.created_at.desc()).limit(limit)
    res = await session.execute(stmt)
    records = list(res.scalars().all())
    return [BackupRecordSchema.model_validate(r) for r in records]


@admin_backups_router.get(
    "/restore-drills",
    response_model=list[RestoreDrillRecordSchema],
    summary="List restore drill history",
    description=(
        "Returns read-only history of automated restore drill executions and verification "
        "outcomes. Requires ADMIN role."
    ),
)
async def list_restore_drills(
    session: DbSessionDep,
    limit: int = Query(default=50, ge=1, le=200),
    _admin: object = Depends(RequireRole(Role.ADMIN)),
) -> list[RestoreDrillRecordSchema]:
    """Return historical restore drill execution records."""
    stmt = select(RestoreDrillRecord).order_by(RestoreDrillRecord.started_at.desc()).limit(limit)
    res = await session.execute(stmt)
    records = list(res.scalars().all())
    return [RestoreDrillRecordSchema.model_validate(r) for r in records]


__all__ = ["admin_backups_router"]
