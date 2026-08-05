"""Unit and integration tests for MinIO S3-compatible BackupStorage backend."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError  # type: ignore
from pydantic import ValidationError

from config.settings import Settings
from ops.backup.minio_storage import MinIOBackupStorage
from ops.backup.storage import BackupStorage, LocalBackupStorage, get_backup_storage


def test_settings_validation_minio_disabled() -> None:
    """Verify settings validate when backend is local, even with missing MinIO keys."""
    with patch.dict("os.environ", {"BACKUP_STORAGE_BACKEND": "local"}):
        settings = Settings()
        assert settings.backup_storage_backend == "local"


def test_settings_validation_minio_enabled_success() -> None:
    """Verify settings validate when MinIO is enabled and all parameters are populated."""
    with patch.dict(
        "os.environ",
        {
            "BACKUP_STORAGE_BACKEND": "minio",
            "MINIO_ENDPOINT": "http://localhost:9000",
            "MINIO_ACCESS_KEY": "minioadmin",
            "MINIO_SECRET_KEY": "minioadmin_password",
            "MINIO_BUCKET": "gaiaos-backups",
        },
    ):
        settings = Settings()
        assert settings.backup_storage_backend == "minio"
        assert settings.minio_endpoint == "http://localhost:9000"


def test_settings_validation_minio_missing_params() -> None:
    """Verify settings validation raises error if MinIO credentials/bucket are missing."""
    with patch.dict(
        "os.environ",
        {
            "BACKUP_STORAGE_BACKEND": "minio",
            "MINIO_ENDPOINT": "http://localhost:9000",
            "MINIO_ACCESS_KEY": "",  # Missing
            "MINIO_SECRET_KEY": "minioadmin_password",
            "MINIO_BUCKET": "gaiaos-backups",
        },
    ):
        with pytest.raises(ValidationError) as exc_info:
            Settings()
    assert "MINIO_ACCESS_KEY must be set when BACKUP_STORAGE_BACKEND is minio" in str(
        exc_info.value
    )


def test_get_backup_storage_factory() -> None:
    """Verify that the get_backup_storage factory returns the correct storage backend instance."""
    from config.settings import get_settings

    get_settings.cache_clear()
    with patch.dict("os.environ", {"BACKUP_STORAGE_BACKEND": "local"}):
        storage = get_backup_storage()
        assert isinstance(storage, LocalBackupStorage)

    get_settings.cache_clear()
    with patch.dict(
        "os.environ",
        {
            "BACKUP_STORAGE_BACKEND": "minio",
            "MINIO_ENDPOINT": "http://localhost:9000",
            "MINIO_ACCESS_KEY": "minioadmin",
            "MINIO_SECRET_KEY": "minioadmin_password",
            "MINIO_BUCKET": "gaiaos-backups",
        },
    ):
        storage = get_backup_storage()
        assert isinstance(storage, MinIOBackupStorage)

    get_settings.cache_clear()


def test_storage_interface_parity() -> None:
    """Verify LocalBackupStorage and MinIOBackupStorage satisfy BackupStorage protocol."""
    # Type checking validation: mypy enforces this, but we also verify runtime protocol matches
    local_storage = LocalBackupStorage()
    minio_storage = MinIOBackupStorage()

    assert isinstance(local_storage, BackupStorage)
    assert isinstance(minio_storage, BackupStorage)

    # Verify matching method signatures
    for method_name in ["upload", "download", "delete", "list_backups"]:
        assert hasattr(local_storage, method_name)
        assert hasattr(minio_storage, method_name)


@pytest.mark.asyncio
async def test_minio_lazy_initialization_and_client_creation() -> None:
    """Verify S3 client is initialized lazily only on operations, not at instantiation."""
    with patch("boto3.Session") as mock_session_class:
        storage = MinIOBackupStorage()
        # Verify Session has not been created yet
        mock_session_class.assert_not_called()

        # Mock the client interactions
        mock_client = MagicMock()
        mock_session = MagicMock()
        mock_session.client.return_value = mock_client
        mock_session_class.return_value = mock_session

        # Mock head_bucket to simulate bucket already exists
        mock_client.head_bucket.return_value = {}

        # Settings mock
        mock_settings = MagicMock()
        mock_settings.backup_storage_backend = "minio"
        mock_settings.minio_endpoint = "http://localhost:9000"
        mock_settings.minio_access_key = "minioadmin"
        mock_settings.minio_secret_key = "minioadmin_password"
        mock_settings.minio_bucket = "gaiaos-backups"
        mock_settings.minio_secure = False
        mock_settings.minio_auto_create_bucket = True

        with patch("ops.backup.minio_storage.get_settings", return_value=mock_settings):
            # Try to list backups
            keys = await storage.list_backups()
            assert isinstance(keys, list)

            # Now verify session and client were initialized
            mock_session_class.assert_called_once()
            mock_client.head_bucket.assert_called_once_with(Bucket="gaiaos-backups")


@pytest.mark.asyncio
async def test_minio_auto_create_bucket_enabled() -> None:
    """Verify bucket is created automatically when missing and auto-creation is enabled."""
    with patch("boto3.Session") as mock_session_class:
        storage = MinIOBackupStorage()

        mock_client = MagicMock()
        mock_session = MagicMock()
        mock_session.client.return_value = mock_client
        mock_session_class.return_value = mock_session

        # Simulate NoSuchBucket / 404 error during head_bucket
        err_response = {"Error": {"Code": "404", "Message": "Not Found"}}
        mock_client.head_bucket.side_effect = ClientError(err_response, "HeadBucket")

        # Settings mock
        mock_settings = MagicMock()
        mock_settings.backup_storage_backend = "minio"
        mock_settings.minio_endpoint = "http://localhost:9000"
        mock_settings.minio_access_key = "minioadmin"
        mock_settings.minio_secret_key = "minioadmin_password"
        mock_settings.minio_bucket = "gaiaos-backups"
        mock_settings.minio_secure = False
        mock_settings.minio_auto_create_bucket = True

        with patch("ops.backup.minio_storage.get_settings", return_value=mock_settings):
            await storage.list_backups()
            # Verify create_bucket was called
            mock_client.create_bucket.assert_called_once_with(Bucket="gaiaos-backups")


@pytest.mark.asyncio
async def test_minio_auto_create_bucket_disabled() -> None:
    """Verify that ValueError is raised when bucket is missing and auto-creation is disabled."""
    with patch("boto3.Session") as mock_session_class:
        storage = MinIOBackupStorage()

        mock_client = MagicMock()
        mock_session = MagicMock()
        mock_session.client.return_value = mock_client
        mock_session_class.return_value = mock_session

        err_response = {"Error": {"Code": "NoSuchBucket", "Message": "Not Found"}}
        mock_client.head_bucket.side_effect = ClientError(err_response, "HeadBucket")

        # Settings mock
        mock_settings = MagicMock()
        mock_settings.backup_storage_backend = "minio"
        mock_settings.minio_endpoint = "http://localhost:9000"
        mock_settings.minio_access_key = "minioadmin"
        mock_settings.minio_secret_key = "minioadmin_password"
        mock_settings.minio_bucket = "gaiaos-backups"
        mock_settings.minio_secure = False
        mock_settings.minio_auto_create_bucket = False

        with patch("ops.backup.minio_storage.get_settings", return_value=mock_settings):
            with pytest.raises(ValueError) as exc_info:
                await storage.list_backups()
            assert "does not exist and auto-creation is disabled" in str(exc_info.value)
            mock_client.create_bucket.assert_not_called()


@pytest.mark.asyncio
async def test_minio_upload_download_lifecycle(tmp_path: Path) -> None:
    """Verify S3 streaming upload and download calls boto3 client methods correctly."""
    with patch("boto3.Session") as mock_session_class:
        storage = MinIOBackupStorage()

        mock_client = MagicMock()
        mock_session = MagicMock()
        mock_session.client.return_value = mock_client
        mock_session_class.return_value = mock_session
        mock_client.head_bucket.return_value = {}

        # Settings mock
        mock_settings = MagicMock()
        mock_settings.backup_storage_backend = "minio"
        mock_settings.minio_endpoint = "http://localhost:9000"
        mock_settings.minio_access_key = "minioadmin"
        mock_settings.minio_secret_key = "minioadmin_password"
        mock_settings.minio_bucket = "gaiaos-backups"
        mock_settings.minio_secure = False
        mock_settings.minio_auto_create_bucket = True
        mock_settings.resilience_bypass = True

        # Create dummy file to upload
        local_file = tmp_path / "test_backup.sql"
        local_file.write_text("SELECT 1;")

        download_file = tmp_path / "downloaded_backup.sql"

        with patch("ops.backup.minio_storage.get_settings", return_value=mock_settings):
            # 1. Test Upload
            s3_uri = await storage.upload(local_file, "test_backup.sql")
            assert s3_uri == "s3://gaiaos-backups/test_backup.sql"
            mock_client.upload_fileobj.assert_called_once()

            # Verify content type and metadata args in upload_fileobj call
            call_args = mock_client.upload_fileobj.call_args[1]
            assert "ExtraArgs" in call_args
            extra_args = call_args["ExtraArgs"]
            assert extra_args["ContentType"] == "application/x-sql"
            assert "checksum" in extra_args["Metadata"]
            assert "created_timestamp" in extra_args["Metadata"]

            # 2. Test Download
            await storage.download("test_backup.sql", download_file)
            mock_client.download_fileobj.assert_called_once()

            # 3. Test Delete
            await storage.delete("test_backup.sql")
            mock_client.delete_object.assert_called_once_with(
                Bucket="gaiaos-backups", Key="test_backup.sql"
            )


@pytest.mark.asyncio
async def test_minio_forbidden_fails_immediately() -> None:
    """Verify that a 403 Forbidden error from head_bucket fails without attempting creation."""
    with patch("boto3.Session") as mock_session_class:
        storage = MinIOBackupStorage()

        mock_client = MagicMock()
        mock_session = MagicMock()
        mock_session.client.return_value = mock_client
        mock_session_class.return_value = mock_session

        # Simulate 403 Forbidden error during head_bucket
        err_response = {"Error": {"Code": "403", "Message": "Forbidden"}}
        mock_client.head_bucket.side_effect = ClientError(err_response, "HeadBucket")

        # Settings mock
        mock_settings = MagicMock()
        mock_settings.backup_storage_backend = "minio"
        mock_settings.minio_endpoint = "http://localhost:9000"
        mock_settings.minio_access_key = "minioadmin"
        mock_settings.minio_secret_key = "minioadmin_password"
        mock_settings.minio_bucket = "gaiaos-backups"
        mock_settings.minio_secure = False
        mock_settings.minio_auto_create_bucket = True

        with patch("ops.backup.minio_storage.get_settings", return_value=mock_settings):
            with pytest.raises(RuntimeError) as exc_info:
                await storage.list_backups()
            assert "Failed to list backups" in str(exc_info.value)
            mock_client.create_bucket.assert_not_called()
