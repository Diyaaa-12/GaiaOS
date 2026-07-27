"""Unit tests for backup storage abstraction, provider, retention cleanup, and worker jobs."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from db.models.backup_record import BackupStatus
from ops.backup.postgres_backup import cleanup_expired_backups, run_postgres_backup
from ops.backup.redis_backup import verify_redis_snapshot
from ops.backup.storage import LocalBackupStorage
from workers.jobs.backup_jobs import (
    run_postgres_backup_job,
    run_redis_verification_job,
)


@pytest.mark.asyncio
async def test_local_backup_storage_operations() -> None:
    """Verify LocalBackupStorage upload, download, list, and delete operations."""
    with tempfile.TemporaryDirectory() as temp_dir:
        storage = LocalBackupStorage(base_dir=temp_dir)

        # 1. Create a dummy local file
        src_file = Path(temp_dir) / "source_dump.sql"
        src_file.write_text("SELECT 1;")

        # 2. Upload
        remote_key = "20260727/dump.sql"
        dest_str = await storage.upload(src_file, remote_key)
        assert Path(dest_str).exists()

        # 3. List
        backups = await storage.list_backups()
        assert "20260727/dump.sql" in backups

        # 4. Download
        dl_file = Path(temp_dir) / "downloaded.sql"
        res_path = await storage.download(remote_key, dl_file)
        assert res_path.exists()
        assert dl_file.read_text() == "SELECT 1;"

        # 5. Delete
        await storage.delete(remote_key)
        assert not Path(dest_str).exists()


@pytest.mark.asyncio
async def test_verify_redis_snapshot() -> None:
    """Verify Redis snapshot integrity checking."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # 1. Non-existent file
        res_missing = verify_redis_snapshot(Path(temp_dir) / "nonexistent.rdb")
        assert not res_missing.exists
        assert not res_missing.valid

        # 2. Valid RDB file
        rdb_file = Path(temp_dir) / "dump.rdb"
        rdb_file.write_bytes(b"REDIS0009\xff\x00\x00\x00\x00")

        res_valid = verify_redis_snapshot(rdb_file, max_age_seconds=3600)
        assert res_valid.exists
        assert res_valid.readable
        assert res_valid.magic_valid
        assert res_valid.valid
        assert len(res_valid.checksum) == 64

        # 3. Stale snapshot file
        res_stale = verify_redis_snapshot(rdb_file, max_age_seconds=-1)
        assert not res_stale.valid
        assert "exceeds limit" in (res_stale.error_message or "")


@pytest.mark.asyncio
async def test_cleanup_expired_backups_transactional() -> None:
    """Verify cleanup_expired_backups transactionally deletes storage file before DB row."""
    mock_storage = AsyncMock()
    mock_session = AsyncMock()

    expired_record = MagicMock()
    expired_record.backup_id = "backup_old_123"

    mock_result = MagicMock()
    mock_result.scalars().all.return_value = [expired_record]
    mock_session.execute.return_value = mock_result

    # 1. Test successful deletion flow
    deleted = await cleanup_expired_backups(mock_storage, mock_session, retention_days=30)
    assert deleted == 1
    mock_storage.delete.assert_called_once_with("backup_old_123.sql")
    mock_session.delete.assert_called_once_with(expired_record)
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_cleanup_expired_backups_rollback_on_storage_failure() -> None:
    """Verify cleanup_expired_backups rolls back DB transaction if storage delete fails."""
    mock_storage = AsyncMock()
    mock_storage.delete.side_effect = RuntimeError("Storage unlink error")
    mock_session = AsyncMock()

    expired_record = MagicMock()
    expired_record.backup_id = "backup_old_456"

    mock_result = MagicMock()
    mock_result.scalars().all.return_value = [expired_record]
    mock_session.execute.return_value = mock_result

    deleted = await cleanup_expired_backups(mock_storage, mock_session, retention_days=30)
    assert deleted == 0
    mock_session.rollback.assert_called()


@pytest.mark.asyncio
async def test_run_postgres_backup_flow() -> None:
    """Verify run_postgres_backup creates backup, stores metadata, and records BackupRecord."""
    with tempfile.TemporaryDirectory() as temp_dir:
        storage = LocalBackupStorage(base_dir=temp_dir)
        mock_provider = AsyncMock()

        def _create_dump(output_path: Path) -> Path:
            output_path.write_text("CREATE TABLE test;")
            return output_path

        mock_provider.create_backup.side_effect = _create_dump
        mock_provider.extract_verification_metadata.return_value = {
            "tables": {"users": {"rows": 5, "sample_checksum": "abc"}},
            "migration_version": "0017",
            "postgres_version": "PostgreSQL 16",
        }

        rec = await run_postgres_backup(storage=storage, provider=mock_provider)

        assert rec.status == BackupStatus.SUCCESS
        assert rec.backup_id.startswith("backup_")
        assert rec.size_bytes > 0
        assert rec.verification_metadata["migration_version"] == "0017"


def test_worker_backup_job_execution() -> None:
    """Verify worker job wrapper calls run_postgres_backup synchronously."""
    with patch("workers.jobs.backup_jobs.run_postgres_backup") as mock_run:
        mock_rec = MagicMock()
        mock_rec.backup_id = "backup_test_123"
        mock_rec.status = BackupStatus.SUCCESS
        mock_rec.size_bytes = 1024
        mock_rec.duration_ms = 150.0
        mock_run.return_value = mock_rec

        res = run_postgres_backup_job()
        assert res["backup_id"] == "backup_test_123"
        assert res["status"] == "SUCCESS"


def test_worker_redis_verification_job() -> None:
    """Verify worker job wrapper calls verify_redis_snapshot."""
    with patch("workers.jobs.backup_jobs.verify_redis_snapshot") as mock_verify:
        mock_res = MagicMock()
        mock_res.exists = True
        mock_res.readable = True
        mock_res.magic_valid = True
        mock_res.checksum = "a" * 64
        mock_res.age_seconds = 10.0
        mock_res.valid = True
        mock_verify.return_value = mock_res

        res = run_redis_verification_job()
        assert res["valid"] is True
        assert res["exists"] is True
