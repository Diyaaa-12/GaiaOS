"""Worker background job orchestration wrappers for automated backups and restore drills."""

from __future__ import annotations

import asyncio

from config.settings import get_settings
from logging_config import configure_logging, get_logger
from ops.backup.postgres_backup import run_postgres_backup
from ops.backup.redis_backup import verify_redis_snapshot
from ops.backup.restore_drill import run_restore_drill

_log = get_logger(__name__)


def run_postgres_backup_job() -> dict[str, str | float]:
    """RQ worker entrypoint for scheduled PostgreSQL backup job."""
    settings = get_settings()
    configure_logging(settings)
    _log.info("worker_job.postgres_backup.start")

    rec = asyncio.run(run_postgres_backup())

    _log.info(
        "worker_job.postgres_backup.completed",
        backup_id=rec.backup_id,
        status=rec.status.value,
        size_bytes=rec.size_bytes,
        duration_ms=rec.duration_ms,
    )

    return {
        "backup_id": rec.backup_id,
        "status": rec.status.value,
        "size_bytes": rec.size_bytes,
        "duration_ms": rec.duration_ms,
    }


def run_restore_drill_job(backup_id: str | None = None) -> dict[str, str | bool | float]:
    """RQ worker entrypoint for scheduled automated restore drill job."""
    settings = get_settings()
    configure_logging(settings)
    _log.info("worker_job.restore_drill.start", backup_id=backup_id)

    rec = asyncio.run(run_restore_drill(backup_id=backup_id))

    _log.info(
        "worker_job.restore_drill.completed",
        drill_id=rec.drill_id,
        backup_id=rec.backup_id,
        status=rec.status.value,
        duration_ms=rec.duration_ms,
    )

    return {
        "drill_id": rec.drill_id,
        "backup_id": rec.backup_id,
        "status": rec.status.value,
        "row_counts_match": rec.row_counts_match,
        "checksum_match": rec.checksum_match,
        "migration_version_match": rec.migration_version_match,
        "duration_ms": rec.duration_ms,
    }


def run_redis_verification_job(snapshot_path: str | None = None) -> dict[str, str | bool | float]:
    """RQ worker entrypoint for Redis snapshot integrity verification job."""
    settings = get_settings()
    configure_logging(settings)
    _log.info("worker_job.redis_verification.start", snapshot_path=snapshot_path)

    result = verify_redis_snapshot(snapshot_path=snapshot_path)

    _log.info(
        "worker_job.redis_verification.completed",
        valid=result.valid,
        exists=result.exists,
        checksum=result.checksum[:12],
    )

    return {
        "exists": result.exists,
        "readable": result.readable,
        "magic_valid": result.magic_valid,
        "checksum": result.checksum,
        "age_seconds": result.age_seconds,
        "valid": result.valid,
    }
