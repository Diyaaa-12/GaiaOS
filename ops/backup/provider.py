"""Database backup provider protocol and PostgreSQL implementation."""

from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Protocol

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.sql.elements import quoted_name

from logging_config import get_logger

_log = get_logger(__name__)


class DatabaseBackupProvider(Protocol):
    """Protocol for database backup and restore provider implementations."""

    async def create_backup(self, output_path: Path) -> Path:
        """Create a local database dump file at output_path."""
        ...

    async def restore_backup(self, input_path: Path, target_db_url: str) -> None:
        """Restore a local database dump file into target_db_url."""
        ...

    async def extract_verification_metadata(self, db_url: str) -> dict[str, Any]:
        """Extract table metrics, sample checksums, migration version, and version string."""
        ...


class PostgresBackupProvider:
    """PostgreSQL implementation of DatabaseBackupProvider using pg_dump / psql."""

    def __init__(self, db_url: str) -> None:
        self.db_url = db_url

    async def create_backup(self, output_path: Path) -> Path:
        """Execute pg_dump against the configured database URL."""
        _log.info("postgres_provider.create_backup", output_path=str(output_path))
        pg_dump_bin = shutil.which("pg_dump")
        if not pg_dump_bin:
            raise RuntimeError(
                "pg_dump executable not found in system PATH. "
                "PostgreSQL backup requires pg_dump to be installed and available."
            )

        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Build pg_dump command using database URL
        cmd = [
            pg_dump_bin,
            "--dbname",
            self.db_url,
            "--clean",
            "--if-exists",
            "--format=plain",
            "--file",
            str(output_path),
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            err_msg = stderr.decode().strip()
            _log.error(
                "postgres_provider.dump_failed",
                returncode=proc.returncode,
                error=err_msg,
            )
            raise RuntimeError(f"pg_dump failed with code {proc.returncode}: {err_msg}")

        return output_path

    async def restore_backup(self, input_path: Path, target_db_url: str) -> None:
        """Restore a plain-text SQL dump into target_db_url using psql."""
        _log.info(
            "postgres_provider.restore_backup",
            input_path=str(input_path),
            target_db_url=target_db_url,
        )
        if not input_path.exists():
            raise FileNotFoundError(f"Backup dump file not found: {input_path}")

        psql_bin = shutil.which("psql")
        if not psql_bin:
            raise RuntimeError(
                "psql executable not found in system PATH. "
                "Database restore requires psql to be installed and available."
            )

        cmd = [psql_bin, "--dbname", target_db_url, "--file", str(input_path)]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            err_msg = stderr.decode().strip()
            _log.warning(
                "postgres_provider.psql_warning",
                returncode=proc.returncode,
                error=err_msg,
            )

    async def extract_verification_metadata(self, db_url: str) -> dict[str, Any]:
        """Query database for row counts, sample checksums, Alembic version, and server version."""
        _log.info("postgres_provider.extract_metadata", db_url=db_url)
        # Ensure asyncpg driver URL
        async_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
        engine = create_async_engine(async_url, echo=False)

        tables_to_audit = [
            "users",
            "investigations",
            "hazard_events",
            "alert_rules",
            "alert_incidents",
            "api_keys",
            "password_reset_tokens",
            "metric_events",
        ]

        table_metadata: dict[str, dict[str, Any]] = {}
        migration_version = "unknown"
        pg_version = "PostgreSQL"

        async with engine.connect() as conn:
            # Query PostgreSQL version
            try:
                res = await conn.execute(text("SELECT version();"))
                val = res.scalar()
                if val:
                    pg_version = str(val).split()[0] + " " + str(val).split()[1]
            except Exception:
                pass

            # Query current Alembic migration version
            try:
                res = await conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1;"))
                val = res.scalar()
                if val:
                    migration_version = str(val)
            except Exception:
                pass

            # Query row counts and sample checksums for each table with safely quoted identifiers
            for table_name in tables_to_audit:
                safe_table = quoted_name(table_name, quote=True)
                try:
                    res_count = await conn.execute(text(f"SELECT COUNT(*) FROM {safe_table};"))  # noqa: S608
                    row_count = int(res_count.scalar() or 0)

                    res_sample = await conn.execute(text(f"SELECT * FROM {safe_table} LIMIT 100;"))  # noqa: S608
                    rows = res_sample.mappings().all()

                    sample_data = json.dumps(
                        [dict(r) for r in rows],
                        sort_keys=True,
                        separators=(",", ":"),
                        default=str,
                    )
                    sample_checksum = hashlib.sha256(sample_data.encode()).hexdigest()

                    table_metadata[table_name] = {
                        "rows": row_count,
                        "sample_checksum": sample_checksum,
                        "sample_size": len(rows),
                    }
                except Exception:
                    # Table might not exist yet
                    continue

        await engine.dispose()

        return {
            "tables": table_metadata,
            "migration_version": migration_version,
            "postgres_version": pg_version,
        }
