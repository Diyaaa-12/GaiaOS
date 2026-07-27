"""Automated restore drill runner.

Verifies restored scratch database metrics against immutable backup metadata.
"""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine

from config.settings import get_settings
from db.models.backup_record import BackupRecord, BackupStatus, RestoreDrillRecord
from db.session import get_session_factory
from logging_config import get_logger
from metrics.collector import emit, persist_metric
from metrics.events import RestoreDrillCompleted, RestoreDrillFailed
from ops.backup.provider import DatabaseBackupProvider, PostgresBackupProvider
from ops.backup.storage import BackupStorage, LocalBackupStorage

_log = get_logger(__name__)


async def _create_scratch_database(admin_db_url: str, scratch_db_name: str) -> str:
    """Create a fresh isolated scratch database for restore verification."""
    async_admin_url = admin_db_url.replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(async_admin_url, isolation_level="AUTOCOMMIT")

    try:
        async with engine.connect() as conn:
            _log.info("restore_drill.create_scratch_db", scratch_db_name=scratch_db_name)
            await conn.execute(text(f'DROP DATABASE IF EXISTS "{scratch_db_name}";'))
            await conn.execute(text(f'CREATE DATABASE "{scratch_db_name}";'))
    except Exception as exc:
        _log.error("restore_drill.create_scratch_db_failed", error=str(exc))
        raise PermissionError(
            f"Failed to create scratch database '{scratch_db_name}'. "
            "Restore drills require CREATEDB privileges on PostgreSQL host. "
            f"Details: {str(exc)}"
        ) from exc
    finally:
        await engine.dispose()

    # Build target scratch database connection URL
    base_parts = admin_db_url.rsplit("/", 1)
    return f"{base_parts[0]}/{scratch_db_name}"


async def _drop_scratch_database(admin_db_url: str, scratch_db_name: str) -> None:
    """Destroy scratch database after restore verification completes."""
    async_admin_url = admin_db_url.replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(async_admin_url, isolation_level="AUTOCOMMIT")

    async with engine.connect() as conn:
        _log.info("restore_drill.drop_scratch_db", scratch_db_name=scratch_db_name)
        # Terminate active connections to scratch database before dropping
        await conn.execute(
            text(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                f"WHERE datname = '{scratch_db_name}' AND pid <> pg_backend_pid();"
            )
        )
        await conn.execute(text(f'DROP DATABASE IF EXISTS "{scratch_db_name}";'))

    await engine.dispose()


async def run_restore_drill(
    backup_id: str | None = None,
    storage: BackupStorage | None = None,
    provider: DatabaseBackupProvider | None = None,
    target_db_name: str | None = None,
) -> RestoreDrillRecord:
    """Execute automated restore drill into an isolated fresh scratch DB.

    Verifies restored database metrics against stored immutable backup metadata.
    """
    start_time = time.monotonic()
    settings = get_settings()
    session_factory = get_session_factory()

    if not settings.database_url:
        raise RuntimeError(
            "DATABASE_URL environment variable is not configured. "
            "Restore drill cannot execute without an explicit connection URL."
        )

    storage_backend = storage or LocalBackupStorage(base_dir=settings.backup_storage_path)
    main_db_url = settings.database_url

    drill_id = f"drill_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

    # 1. Fetch latest successful backup record
    target_backup_record: BackupRecord | None = None
    async with session_factory() as session:
        if backup_id:
            stmt = select(BackupRecord).where(BackupRecord.backup_id == backup_id)
        else:
            stmt = (
                select(BackupRecord)
                .where(BackupRecord.status == BackupStatus.SUCCESS)
                .order_by(BackupRecord.created_at.desc())
            )
        res = await session.execute(stmt)
        target_backup_record = res.scalars().first()

    if not target_backup_record or target_backup_record.status != BackupStatus.SUCCESS:
        err_msg = f"No successful backup found for restore drill (requested backup_id={backup_id})"
        _log.error("restore_drill.no_successful_backup", error=err_msg)

        async with session_factory() as session:
            fail_rec = RestoreDrillRecord(
                drill_id=drill_id,
                backup_id=backup_id or "unknown",
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                status=BackupStatus.FAILED,
                error_details=err_msg,
            )
            session.add(fail_rec)
            await session.commit()
            return fail_rec

    selected_backup_id = target_backup_record.backup_id
    expected_metadata = target_backup_record.verification_metadata or {}

    # 2. Record drill state PENDING -> RUNNING
    async with session_factory() as session:
        drill_rec = RestoreDrillRecord(
            drill_id=drill_id,
            backup_id=selected_backup_id,
            started_at=datetime.now(UTC),
            status=BackupStatus.PENDING,
        )
        session.add(drill_rec)
        await session.commit()
        await session.refresh(drill_rec)

        drill_rec.status = BackupStatus.RUNNING
        await session.commit()

    _log.info("restore_drill.started", drill_id=drill_id, backup_id=selected_backup_id)

    scratch_db_name = target_db_name or f"gaiaos_scratch_{uuid.uuid4().hex[:8]}"
    temp_dir = (Path(settings.backup_storage_path) / "temp").resolve()
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_download_path = temp_dir / f"{selected_backup_id}_restore.sql"

    scratch_db_url: str | None = None

    try:
        # 3. Download backup dump file from storage
        remote_key = f"{selected_backup_id}.sql"
        local_dump_path = await storage_backend.download(remote_key, temp_download_path)

        # 4. Create fresh scratch DB
        scratch_db_url = await _create_scratch_database(main_db_url, scratch_db_name)

        backup_provider = provider or PostgresBackupProvider(db_url=scratch_db_url)

        # 5. Restore dump into scratch DB
        await backup_provider.restore_backup(local_dump_path, scratch_db_url)

        # 6. Extract restored scratch DB verification metadata
        extracted_metadata = await backup_provider.extract_verification_metadata(scratch_db_url)

        # 7. Triple-Check Verification against stored immutable backup metadata
        expected_tables = expected_metadata.get("tables", {})
        extracted_tables = extracted_metadata.get("tables", {})

        row_counts_match = True
        checksum_match = True
        discrepancies: dict[str, Any] = {}

        for tbl, exp_info in expected_tables.items():
            ext_info = extracted_tables.get(tbl, {})
            exp_rows = exp_info.get("rows", 0)
            ext_rows = ext_info.get("rows", 0)

            if exp_rows != ext_rows:
                row_counts_match = False
                discrepancies[f"table_{tbl}_rows"] = f"Expected {exp_rows}, got {ext_rows}"

            exp_cs = exp_info.get("sample_checksum", "")
            ext_cs = ext_info.get("sample_checksum", "")
            if exp_cs and ext_cs and exp_cs != ext_cs:
                checksum_match = False
                discrepancies[f"table_{tbl}_checksum"] = f"Expected {exp_cs[:8]}, got {ext_cs[:8]}"

        expected_mig = expected_metadata.get("migration_version", "")
        extracted_mig = extracted_metadata.get("migration_version", "")
        migration_version_match = (expected_mig == extracted_mig) if expected_mig else True

        if not migration_version_match:
            discrepancies["migration_version"] = f"Expected {expected_mig}, got {extracted_mig}"

        overall_success = row_counts_match and checksum_match and migration_version_match

        duration_ms = (time.monotonic() - start_time) * 1000.0

        # 8. Record RestoreDrillRecord outcome
        async with session_factory() as session:
            stmt_drill = select(RestoreDrillRecord).where(RestoreDrillRecord.drill_id == drill_id)
            res_drill = await session.execute(stmt_drill)
            drill_rec = res_drill.scalar_one()

            drill_rec.status = BackupStatus.SUCCESS if overall_success else BackupStatus.FAILED
            drill_rec.completed_at = datetime.now(UTC)
            drill_rec.duration_ms = duration_ms
            drill_rec.row_counts_match = row_counts_match
            drill_rec.checksum_match = checksum_match
            drill_rec.migration_version_match = migration_version_match
            drill_rec.discrepancies = discrepancies
            if not overall_success:
                drill_rec.error_details = f"Verification discrepancies detected: {discrepancies}"
            await session.commit()
            await session.refresh(drill_rec)
            final_record: RestoreDrillRecord = drill_rec

        # 9. Emit metrics
        if overall_success:
            event = RestoreDrillCompleted(
                drill_id=drill_id,
                backup_id=selected_backup_id,
                duration_ms=duration_ms,
                success=True,
            )
            emit(event)
            async with session_factory() as session:
                await persist_metric(session, event)
                await session.commit()
        else:
            fail_event = RestoreDrillFailed(
                drill_id=drill_id,
                backup_id=selected_backup_id,
                duration_ms=duration_ms,
                error_message=f"Restore drill failed verification: {discrepancies}",
                discrepancies=discrepancies,
            )
            emit(fail_event)
            async with session_factory() as session:
                await persist_metric(session, fail_event)
                await session.commit()

        return final_record

    except Exception as exc:
        duration_ms = (time.monotonic() - start_time) * 1000.0
        err_msg = str(exc)
        _log.error("restore_drill.failed", drill_id=drill_id, error=err_msg)

        async with session_factory() as session:
            stmt_drill = select(RestoreDrillRecord).where(RestoreDrillRecord.drill_id == drill_id)
            res_drill_fail = await session.execute(stmt_drill)
            rec_fail = res_drill_fail.scalar_one_or_none()
            if rec_fail:
                rec_fail.status = BackupStatus.FAILED
                rec_fail.completed_at = datetime.now(UTC)
                rec_fail.duration_ms = duration_ms
                rec_fail.error_details = err_msg
                await session.commit()
                return rec_fail

        raise

    finally:
        # 10. Destroy scratch database in finally block to ensure clean state
        if scratch_db_url and scratch_db_name and scratch_db_name != "gaiaos":
            try:
                await _drop_scratch_database(main_db_url, scratch_db_name)
            except Exception as e:
                _log.warning("restore_drill.cleanup_scratch_db_failed", error=str(e))

        # Cleanup local downloaded dump file
        if temp_download_path.exists():
            try:
                temp_download_path.unlink()
            except OSError:
                pass
