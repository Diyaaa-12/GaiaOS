"""MinIO S3-compatible implementation of BackupStorage."""

from __future__ import annotations

import asyncio
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import boto3  # type: ignore
import botocore.config  # type: ignore
import botocore.exceptions  # type: ignore
import httpx

from config.settings import get_settings
from logging_config import get_logger
from ops.backup.storage import compute_file_sha256
from resilience.degraded_mode import ResilientResult, resilient_call

_log = get_logger(__name__)


async def _execute_s3_call[T](func: Any) -> T:
    """Execute a synchronous S3/boto3 function in an executor.

    Maps S3/botocore exceptions to httpx.HTTPError so that the shared
    resilience layer (resilient_call) can detect and handle them.
    """
    try:
        return await asyncio.to_thread(func)
    except (botocore.exceptions.BotoCoreError, botocore.exceptions.ClientError) as exc:
        raise httpx.HTTPError(f"MinIO S3 operation failed: {str(exc)}") from exc


class MinIOBackupStorage:
    """S3-compatible object storage implementation of BackupStorage (MinIO)."""

    def __init__(self) -> None:
        self._client = None
        self._lock = threading.Lock()

    def _get_client(self) -> Any:
        """Thread-safe lazy initialization of the boto3 S3 client.

        Performs lazy bucket verification and optional auto-creation.
        """
        with self._lock:
            if self._client is not None:
                return self._client

            settings = get_settings()

            # Initialize S3 client using boto3 session
            session = boto3.Session()
            client = session.client(
                "s3",
                endpoint_url=settings.minio_endpoint,
                aws_access_key_id=settings.minio_access_key,
                aws_secret_access_key=settings.minio_secret_key,
                use_ssl=settings.minio_secure,
                config=botocore.config.Config(
                    signature_version="s3v4",
                    connect_timeout=10,
                    read_timeout=30,
                ),
            )

            # Verify and optionally create bucket
            bucket = settings.minio_bucket
            try:
                client.head_bucket(Bucket=bucket)
            except botocore.exceptions.ClientError as exc:
                error_code = str(exc.response.get("Error", {}).get("Code", ""))
                # S3 head_bucket can return 404 (Not Found) or NoSuchBucket if missing
                if error_code in ("404", "NoSuchBucket"):
                    if settings.minio_auto_create_bucket:
                        _log.info("minio_storage.bucket_creating", bucket=bucket)
                        client.create_bucket(Bucket=bucket)
                    else:
                        raise ValueError(
                            f"MinIO bucket '{bucket}' does not exist and "
                            "auto-creation is disabled (MINIO_AUTO_CREATE_BUCKET=false)."
                        ) from exc
                else:
                    raise

            self._client = client
            return self._client

    async def upload(self, local_path: Path, remote_key: str) -> str:
        """Upload local file to MinIO bucket using streaming upload_fileobj."""
        settings = get_settings()
        bucket = settings.minio_bucket

        checksum = compute_file_sha256(local_path)
        timestamp = datetime.now(UTC).isoformat()

        extra_args: dict[str, Any] = {
            "Metadata": {
                "checksum": checksum,
                "created_timestamp": timestamp,
            }
        }

        # Select content-type based on file extension
        if remote_key.endswith(".gz"):
            extra_args["ContentType"] = "application/gzip"
        elif remote_key.endswith(".json"):
            extra_args["ContentType"] = "application/json"
        elif remote_key.endswith(".sql"):
            extra_args["ContentType"] = "application/x-sql"

        def _upload() -> None:
            client = self._get_client()
            with open(local_path, "rb") as f:
                client.upload_fileobj(
                    f,
                    bucket,
                    remote_key,
                    ExtraArgs=extra_args,
                )

        _log.info("minio_storage.upload.start", local_path=str(local_path), remote_key=remote_key)
        res: ResilientResult[None] = await resilient_call(
            source="minio",
            fn=lambda: _execute_s3_call(_upload),
            cache_key=f"upload:{remote_key}",
            ttl=3600,
        )

        if res.degraded and res.source_status == "unavailable":
            raise RuntimeError(f"Failed to upload {remote_key} to MinIO bucket '{bucket}'.")

        return f"s3://{bucket}/{remote_key}"

    async def download(self, remote_key: str, local_path: Path) -> Path:
        """Download file from MinIO bucket to local_path using streaming download_fileobj."""
        settings = get_settings()
        bucket = settings.minio_bucket

        local_path.parent.mkdir(parents=True, exist_ok=True)

        def _download() -> None:
            client = self._get_client()
            with open(local_path, "wb") as f:
                client.download_fileobj(bucket, remote_key, f)

        _log.info("minio_storage.download.start", remote_key=remote_key, local_path=str(local_path))
        res: ResilientResult[None] = await resilient_call(
            source="minio",
            fn=lambda: _execute_s3_call(_download),
            cache_key=f"download:{remote_key}",
            ttl=3600,
        )

        if res.degraded and res.source_status == "unavailable":
            if local_path.exists():
                try:
                    local_path.unlink()
                except OSError:
                    pass
            raise RuntimeError(f"Failed to download {remote_key} from MinIO bucket '{bucket}'.")

        return local_path

    async def delete(self, remote_key: str) -> None:
        """Delete file associated with remote_key from MinIO bucket."""
        settings = get_settings()
        bucket = settings.minio_bucket

        def _delete() -> None:
            client = self._get_client()
            client.delete_object(Bucket=bucket, Key=remote_key)

        _log.info("minio_storage.delete.start", remote_key=remote_key)
        res: ResilientResult[None] = await resilient_call(
            source="minio",
            fn=lambda: _execute_s3_call(_delete),
            cache_key=f"delete:{remote_key}",
            ttl=3600,
        )

        if res.degraded and res.source_status == "unavailable":
            raise RuntimeError(f"Failed to delete {remote_key} from MinIO bucket '{bucket}'.")

    async def list_backups(self) -> list[str]:
        """List all available object keys in the MinIO bucket."""
        settings = get_settings()
        bucket = settings.minio_bucket

        def _list() -> list[str]:
            client = self._get_client()
            response = client.list_objects_v2(Bucket=bucket)
            contents = response.get("Contents", [])
            return [obj["Key"] for obj in contents if "Key" in obj]

        _log.info("minio_storage.list.start")
        res: ResilientResult[list[str]] = await resilient_call(
            source="minio",
            fn=lambda: _execute_s3_call(_list),
            cache_key="list_backups",
            ttl=600,
        )

        if res.degraded and res.source_status == "unavailable":
            raise RuntimeError(f"Failed to list backups in MinIO bucket '{bucket}'.")

        return res.value or []
