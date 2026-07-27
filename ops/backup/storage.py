"""Backup storage protocol and local filesystem implementation."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Protocol

from logging_config import get_logger

_log = get_logger(__name__)


class BackupStorage(Protocol):
    """Protocol abstraction for backup file storage backends."""

    async def upload(self, local_path: Path, remote_key: str) -> str:
        """Upload local file to storage under remote_key. Returns storage location string."""
        ...

    async def download(self, remote_key: str, local_path: Path) -> Path:
        """Download file from remote_key to local_path. Returns local_path."""
        ...

    async def delete(self, remote_key: str) -> None:
        """Delete file associated with remote_key from storage."""
        ...

    async def list_backups(self) -> list[str]:
        """List all available backup remote_keys in storage."""
        ...


class LocalBackupStorage:
    """Local filesystem implementation of BackupStorage."""

    def __init__(self, base_dir: str | Path = "./backups") -> None:
        self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    async def upload(self, local_path: Path, remote_key: str) -> str:
        """Copy local_path to storage directory under remote_key."""
        dest_path = self.base_dir / remote_key
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        _log.info("local_storage.upload", local_path=str(local_path), dest_path=str(dest_path))

        if local_path.resolve() != dest_path.resolve():
            shutil.copy2(local_path, dest_path)

        return str(dest_path)

    async def download(self, remote_key: str, local_path: Path) -> Path:
        """Copy remote_key file from storage directory to local_path."""
        src_path = self.base_dir / remote_key
        if not src_path.exists():
            raise FileNotFoundError(f"Backup file not found in storage: {src_path}")

        _log.info("local_storage.download", src_path=str(src_path), local_path=str(local_path))
        local_path.parent.mkdir(parents=True, exist_ok=True)

        if src_path.resolve() != local_path.resolve():
            shutil.copy2(src_path, local_path)

        return local_path

    async def delete(self, remote_key: str) -> None:
        """Remove file under remote_key from storage directory if it exists."""
        target_path = self.base_dir / remote_key
        _log.info("local_storage.delete", target_path=str(target_path))
        if target_path.exists():
            try:
                target_path.unlink()
            except OSError as exc:
                _log.warning(
                    "local_storage.delete_failed",
                    target_path=str(target_path),
                    error=str(exc),
                )
                raise

    async def list_backups(self) -> list[str]:
        """List all relative file keys in the base storage directory."""
        if not self.base_dir.exists():
            return []
        keys = [
            str(p.relative_to(self.base_dir)).replace("\\", "/")
            for p in self.base_dir.glob("**/*")
            if p.is_file()
        ]
        return keys
