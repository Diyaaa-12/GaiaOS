"""Redis RDB / AOF snapshot integrity verification tooling."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from logging_config import get_logger
from ops.backup.storage import compute_file_sha256

_log = get_logger(__name__)


@dataclass
class SnapshotVerificationResult:
    """Structured result of a Redis snapshot integrity check."""

    exists: bool
    readable: bool
    magic_valid: bool
    checksum: str
    age_seconds: float
    valid: bool
    error_message: str | None = None


def verify_redis_snapshot(
    snapshot_path: Path | str | None = None,
    max_age_seconds: int = 86400,
) -> SnapshotVerificationResult:
    """Verify Redis RDB / AOF snapshot file existence, magic header, SHA256 checksum, and age limit.

    Criteria for valid snapshot:
    1. File exists on disk.
    2. File is readable and non-empty.
    3. File contains valid magic header ('REDIS' for RDB files).
    4. File modification age is within max_age_seconds limit.
    """
    path_obj: Path
    if snapshot_path is not None:
        path_obj = Path(snapshot_path).resolve()
    else:
        # Default fallback path for Redis RDB
        path_obj = Path("./data/dump.rdb").resolve()

    _log.info(
        "redis_backup.verify.start",
        snapshot_path=str(path_obj),
        max_age_seconds=max_age_seconds,
    )

    if not path_obj.exists():
        _log.warning("redis_backup.verify.missing", snapshot_path=str(path_obj))
        return SnapshotVerificationResult(
            exists=False,
            readable=False,
            magic_valid=False,
            checksum="",
            age_seconds=0.0,
            valid=False,
            error_message=f"Snapshot file not found: {path_obj}",
        )

    # 1. Check readability & size
    try:
        size_bytes = path_obj.stat().st_size
        mtime = path_obj.stat().st_mtime
        age_seconds = time.time() - mtime
    except OSError as exc:
        return SnapshotVerificationResult(
            exists=True,
            readable=False,
            magic_valid=False,
            checksum="",
            age_seconds=0.0,
            valid=False,
            error_message=f"Failed to stat snapshot file: {str(exc)}",
        )

    if size_bytes == 0:
        return SnapshotVerificationResult(
            exists=True,
            readable=True,
            magic_valid=False,
            checksum="",
            age_seconds=age_seconds,
            valid=False,
            error_message="Snapshot file is empty (0 bytes)",
        )

    # 2. Check Magic Header & SHA256 Checksum
    magic_valid = False
    try:
        with open(path_obj, "rb") as f:
            header = f.read(5)
            if header == b"REDIS" or path_obj.suffix == ".aof":
                magic_valid = True
        checksum = compute_file_sha256(path_obj)
    except OSError as exc:
        return SnapshotVerificationResult(
            exists=True,
            readable=False,
            magic_valid=False,
            checksum="",
            age_seconds=age_seconds,
            valid=False,
            error_message=f"Error reading snapshot file: {str(exc)}",
        )

    # 3. Check age limit
    if age_seconds > max_age_seconds:
        _log.warning(
            "redis_backup.verify.stale",
            age_seconds=age_seconds,
            max_age_seconds=max_age_seconds,
        )
        return SnapshotVerificationResult(
            exists=True,
            readable=True,
            magic_valid=magic_valid,
            checksum=checksum,
            age_seconds=age_seconds,
            valid=False,
            error_message=f"Snapshot age ({age_seconds:.1f}s) exceeds limit ({max_age_seconds}s)",
        )

    if not magic_valid:
        return SnapshotVerificationResult(
            exists=True,
            readable=True,
            magic_valid=False,
            checksum=checksum,
            age_seconds=age_seconds,
            valid=False,
            error_message="Invalid magic header (expected 'REDIS')",
        )

    _log.info(
        "redis_backup.verify.success",
        checksum=checksum[:12],
        age_seconds=age_seconds,
    )
    return SnapshotVerificationResult(
        exists=True,
        readable=True,
        magic_valid=True,
        checksum=checksum,
        age_seconds=age_seconds,
        valid=True,
        error_message=None,
    )
