"""PostgreSQL logical backup runner and retention enforcement."""

from __future__ import annotations

import hashlib
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import get_settings
from db.models.backup_record import BackupRecord, BackupStatus
from db.session import get_session_factory
from logging_config import get_logger
from metrics.collector import emit, persist_metric
from metrics.events import BackupCompleted
from ops.backup.provider import DatabaseBackupProvider, PostgresBackupProvider
from ops.backup.storage import BackupStorage, LocalBackupStorage

_log = get_logger(__name__)


async def cleanup_expired_backups(
    storage: BackupStorage,
    session: AsyncSession,
    retention_days: int = 30,
) -> int:
    """Purge expired backup files and DB metadata records transactionally.

    First attempts to delete the backup file from BackupStorage.
    Only if file removal succeeds (or file is absent) is the metadata row deleted.
    """
    _log.info("backup.retention_cleanup.start", retention_days=retention_days)
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)

    stmt = select(BackupRecord).where(BackupRecord.created_at < cutoff)
    result = await session.execute(stmt)
    expired_records = list(result.scalars().all())

    deleted_count = 0

    for rec in expired_records:
        remote_key = f"{rec.backup_id}.sql"
        try:
            # 1. Delete file from storage first
            await storage.delete(remote_key)
            _log.info("backup.retention_cleanup.file_deleted", backup_id=rec.backup_id)

            # 2. Transactionally delete metadata row from DB
            await session.delete(rec)
            await session.commit()
            deleted_count += 1
        except Exception as exc:
            await session.rollback()
            _log.warning(
                "backup.retention_cleanup.failed",
                backup_id=rec.backup_id,
                error=str(exc),
            )

    _log.info("backup.retention_cleanup.completed", deleted_count=deleted_count)
    return deleted_count


async def run_postgres_backup(
    storage: BackupStorage | None = None,
    provider: DatabaseBackupProvider | None = None,
) -> BackupRecord:
    """Execute automated PostgreSQL logical backup, extract metadata, and upload to storage."""
    start_time = time.monotonic()
    settings = get_settings()

    if not settings.database_url:
        raise RuntimeError(
            "DATABASE_URL environment variable is not configured. "
            "Database backup cannot execute without an explicit connection URL."
        )

    db_url = settings.database_url
    storage_backend = storage or LocalBackupStorage(base_dir=settings.backup_storage_path)
    backup_provider = provider or PostgresBackupProvider(db_url=db_url)

    backup_id = f"backup_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    temp_dir = (Path(settings.backup_storage_path) / "temp").resolve()
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_dump_path = temp_dir / f"{backup_id}.sql"

    record = BackupRecord(
        backup_id=backup_id,
        created_at=datetime.now(UTC),
        status=BackupStatus.PENDING,
        storage_location=str(settings.backup_storage_path),
    )

    # 1. Record state PENDING -> RUNNING (if DB is accessible)
    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            session.add(record)
            await session.commit()
            await session.refresh(record)

            record.status = BackupStatus.RUNNING
            await session.commit()
    except Exception as db_exc:
        _log.warning("backup.db_record_init_skipped", error=str(db_exc))

    _log.info("backup.started", backup_id=backup_id)

    try:
        # 2. Extract verification metadata before or during backup
        verification_metadata = await backup_provider.extract_verification_metadata(db_url)

        # 3. Create local dump file
        dump_path = await backup_provider.create_backup(temp_dump_path)

        # 4. Compute file size and SHA256 checksum
        size_bytes = dump_path.stat().st_size if dump_path.exists() else 0
        sha256 = hashlib.sha256()
        if dump_path.exists():
            with open(dump_path, "rb") as f:
                while chunk := f.read(65536):
                    sha256.update(chunk)
        checksum = sha256.hexdigest()

        # 5. Upload dump file to BackupStorage
        remote_key = f"{backup_id}.sql"
        storage_location = await storage_backend.upload(dump_path, remote_key)

        # Clean up local temp dump file if distinct from storage
        if dump_path.exists() and dump_path.resolve() != Path(storage_location).resolve():
            try:
                dump_path.unlink()
            except OSError:
                pass

        duration_ms = (time.monotonic() - start_time) * 1000.0
        completed_at = datetime.now(UTC)

        # 6. Mark BackupRecord as SUCCESS
        final_record = record
        try:
            session_factory = get_session_factory()
            async with session_factory() as session:
                stmt = select(BackupRecord).where(BackupRecord.backup_id == backup_id)
                res = await session.execute(stmt)
                rec = res.scalar_one_or_none()
                if rec:
                    rec.status = BackupStatus.SUCCESS
                    rec.completed_at = completed_at
                    rec.size_bytes = size_bytes
                    rec.checksum = checksum
                    rec.storage_location = storage_location
                    rec.postgres_version = verification_metadata.get(
                        "postgres_version", "PostgreSQL"
                    )
                    rec.duration_ms = duration_ms
                    rec.verification_metadata = verification_metadata
                    await session.commit()
                    await session.refresh(rec)
                    final_record = rec
                else:
                    record.status = BackupStatus.SUCCESS
                    record.completed_at = completed_at
                    record.size_bytes = size_bytes
                    record.checksum = checksum
                    record.storage_location = storage_location
                    record.postgres_version = verification_metadata.get(
                        "postgres_version", "PostgreSQL"
                    )
                    record.duration_ms = duration_ms
                    record.verification_metadata = verification_metadata
        except Exception as db_exc:
            _log.warning("backup.db_record_update_skipped", error=str(db_exc))
            record.status = BackupStatus.SUCCESS
            record.completed_at = completed_at
            record.size_bytes = size_bytes
            record.checksum = checksum
            record.storage_location = storage_location
            record.postgres_version = verification_metadata.get("postgres_version", "PostgreSQL")
            record.duration_ms = duration_ms
            record.verification_metadata = verification_metadata

        _log.info(
            "backup.completed",
            backup_id=backup_id,
            size_bytes=size_bytes,
            duration_ms=duration_ms,
        )

        # 7. Telemetry & persistence
        event = BackupCompleted(
            backup_id=backup_id,
            size_bytes=size_bytes,
            duration_ms=duration_ms,
            success=True,
        )
        emit(event)
        try:
            async with session_factory() as session:
                await persist_metric(session, event)
                await session.commit()
        except Exception as db_exc:
            _log.warning("backup.persist_metric_skipped", error=str(db_exc))

        # 8. Retention cleanup
        try:
            async with session_factory() as session:
                await cleanup_expired_backups(
                    storage=storage_backend,
                    session=session,
                    retention_days=settings.backup_retention_days,
                )
        except Exception as db_exc:
            _log.warning("backup.retention_cleanup_skipped", error=str(db_exc))

        return final_record

    except Exception as exc:
        duration_ms = (time.monotonic() - start_time) * 1000.0
        err_msg = str(exc)
        _log.error("backup.failed", backup_id=backup_id, error=err_msg)

        async with session_factory() as session:
            stmt = select(BackupRecord).where(BackupRecord.backup_id == backup_id)
            res_fail = await session.execute(stmt)
            rec_fail = res_fail.scalar_one_or_none()
            if rec_fail:
                rec_fail.status = BackupStatus.FAILED
                rec_fail.completed_at = datetime.now(UTC)
                rec_fail.duration_ms = duration_ms
                rec_fail.error_details = err_msg
                await session.commit()
                return rec_fail

        raise
