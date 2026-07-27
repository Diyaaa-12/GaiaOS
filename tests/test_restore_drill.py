"""Integration and unit tests for automated restore drill execution and verification."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from db.models.backup_record import BackupRecord, BackupStatus
from ops.backup.restore_drill import run_restore_drill
from ops.backup.storage import LocalBackupStorage


@pytest.mark.asyncio
async def test_restore_drill_success_matching_metadata() -> None:
    """Verify restore drill passes when restored scratch DB metadata matches backup metadata."""
    with tempfile.TemporaryDirectory() as temp_dir:
        storage = LocalBackupStorage(base_dir=temp_dir)

        # 1. Prepare dummy backup dump file in storage
        backup_id = "backup_test_success_123"
        dump_file = Path(temp_dir) / f"{backup_id}.sql"
        dump_file.write_text("CREATE TABLE test (id INT);")

        matching_metadata = {
            "tables": {
                "users": {"rows": 10, "sample_checksum": "hash123", "sample_size": 10},
            },
            "migration_version": "0017_backup_records",
            "postgres_version": "PostgreSQL 16",
        }

        # Mock DB Backup Record in Database
        mock_backup_record = BackupRecord(
            backup_id=backup_id,
            status=BackupStatus.SUCCESS,
            verification_metadata=matching_metadata,
        )

        mock_provider = AsyncMock()
        mock_provider.restore_backup.return_value = None
        mock_provider.extract_verification_metadata.return_value = matching_metadata

        test_db_url = "postgresql://postgres:postgres@localhost:5432/gaiaos_scratch"
        with patch("ops.backup.restore_drill.get_session_factory") as mock_sf, \
             patch("ops.backup.restore_drill._create_scratch_database", return_value=test_db_url), \
             patch("ops.backup.restore_drill._drop_scratch_database", return_value=None):

            mock_session = AsyncMock()
            mock_res = MagicMock()
            mock_res.scalars().first.return_value = mock_backup_record

            mock_drill_res = MagicMock()
            mock_drill_rec = MagicMock()
            mock_drill_res.scalar_one.return_value = mock_drill_rec

            mock_session.execute.side_effect = [mock_res, mock_drill_res]
            mock_sf.return_value.return_value.__aenter__.return_value = mock_session

            await run_restore_drill(
                backup_id=backup_id,
                storage=storage,
                provider=mock_provider,
                target_db_name="gaiaos_scratch_test",
            )

            assert mock_drill_rec.status == BackupStatus.SUCCESS
            assert mock_drill_rec.row_counts_match is True
            assert mock_drill_rec.checksum_match is True
            assert mock_drill_rec.migration_version_match is True


@pytest.mark.asyncio
async def test_restore_drill_catches_deliberately_introduced_discrepancy() -> None:
    """Verify restore drill catches deliberately introduced row count / checksum mismatches."""
    with tempfile.TemporaryDirectory() as temp_dir:
        storage = LocalBackupStorage(base_dir=temp_dir)

        backup_id = "backup_test_discrepancy_456"
        dump_file = Path(temp_dir) / f"{backup_id}.sql"
        dump_file.write_text("CREATE TABLE test (id INT);")

        expected_metadata = {
            "tables": {
                "users": {"rows": 100, "sample_checksum": "expected_hash", "sample_size": 100},
            },
            "migration_version": "0017_backup_records",
        }

        # Scratch database returns modified (corrupted/mismatched) row count!
        mismatched_extracted_metadata = {
            "tables": {
                "users": {"rows": 99, "sample_checksum": "corrupted_hash", "sample_size": 99},
            },
            "migration_version": "0017_backup_records",
        }

        mock_backup_record = BackupRecord(
            backup_id=backup_id,
            status=BackupStatus.SUCCESS,
            verification_metadata=expected_metadata,
        )

        mock_provider = AsyncMock()
        mock_provider.restore_backup.return_value = None
        mock_provider.extract_verification_metadata.return_value = mismatched_extracted_metadata

        test_db_url = "postgresql://postgres:postgres@localhost:5432/gaiaos_scratch"
        with patch("ops.backup.restore_drill.get_session_factory") as mock_sf, \
             patch("ops.backup.restore_drill._create_scratch_database", return_value=test_db_url), \
             patch("ops.backup.restore_drill._drop_scratch_database", return_value=None):

            mock_session = AsyncMock()
            mock_res = MagicMock()
            mock_res.scalars().first.return_value = mock_backup_record

            mock_drill_res = MagicMock()
            mock_drill_rec = MagicMock()
            mock_drill_res.scalar_one.return_value = mock_drill_rec

            mock_session.execute.side_effect = [mock_res, mock_drill_res]
            mock_sf.return_value.return_value.__aenter__.return_value = mock_session

            await run_restore_drill(
                backup_id=backup_id,
                storage=storage,
                provider=mock_provider,
                target_db_name="gaiaos_scratch_test",
            )

            # Assert drill catches mismatch and records FAILED status
            assert mock_drill_rec.status == BackupStatus.FAILED
            assert mock_drill_rec.row_counts_match is False
            assert mock_drill_rec.checksum_match is False
            assert "table_users_rows" in mock_drill_rec.discrepancies
            assert "table_users_checksum" in mock_drill_rec.discrepancies
