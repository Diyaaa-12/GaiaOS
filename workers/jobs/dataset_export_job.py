"""Background worker job for monthly public research dataset export — Phase 5 Milestone 9."""

from __future__ import annotations

import asyncio
import gzip
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.api.v1.anonymization import AnonymizationPolicy
from config.settings import get_settings
from db.models.hazard_event import HazardEvent
from db.models.investigation import Investigation
from db.session import AsyncSessionLocal, init_engine
from logging_config import configure_logging, get_logger
from ops.backup.storage import get_backup_storage

_log = get_logger(__name__)


async def _async_run_dataset_export() -> dict[str, Any]:
    """Asynchronous dataset export workflow.

    1. Checks dataset_export_enabled feature flag.
    2. Streams consenting investigations (consent_public_research = True) and hazard_events.
    3. Applies AnonymizationPolicy to all records and streams directly to compressed file.
    4. Writes manifest.json and SHA-256 checksums.
    5. Emits telemetry metrics.
    """
    settings = get_settings()
    configure_logging(settings)

    if not settings.dataset_export_enabled:
        _log.info("dataset_export.job.disabled_by_feature_flag")
        return {"status": "disabled"}

    if settings.database_url and AsyncSessionLocal is None:
        init_engine()

    from db.session import AsyncSessionLocal as session_factory

    if session_factory is None:
        _log.error("dataset_export.job.no_database_session")
        return {"status": "no_database_session"}

    start_time = time.monotonic()
    now_utc = datetime.now(UTC)
    date_str = now_utc.strftime("%Y%m%d_%H%M%S")

    export_dir = Path(settings.dataset_export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)

    archive_filename = f"gaiaos_research_dataset_{date_str}.jsonl.gz"
    archive_path = export_dir / archive_filename
    manifest_path = export_dir / "manifest.json"
    checksum_path = export_dir / f"{archive_filename}.sha256"

    hasher = hashlib.sha256()
    inv_count = 0
    hazard_count = 0

    with gzip.open(archive_path, "wt", encoding="utf-8") as gz:
        async with session_factory() as session:
            # 1. Stream consenting investigations
            inv_stmt = select(Investigation).where(
                Investigation.consent_public_research.is_(True),
                Investigation.status == "complete",
            )
            inv_res = await session.execute(inv_stmt)
            for inv in inv_res.scalars().all():
                anon = AnonymizationPolicy.apply(inv)
                anon["record_type"] = "investigation"
                line = json.dumps(anon) + "\n"
                gz.write(line)
                hasher.update(line.encode("utf-8"))
                inv_count += 1

            # 2. Stream public hazard events
            haz_stmt = select(HazardEvent).limit(1000)
            haz_res = await session.execute(haz_stmt)
            for event in haz_res.scalars().all():
                rec = {
                    "record_type": "hazard_event",
                    "id": str(event.id),
                    "event_type": event.event_type,
                    "region_label": event.region_label,
                    "event_date": event.event_date.isoformat(),
                    "details": event.details,
                    "source": event.source,
                    "external_id": event.external_id,
                }
                line = json.dumps(rec) + "\n"
                gz.write(line)
                hasher.update(line.encode("utf-8"))
                hazard_count += 1

    sha256_hex = hasher.hexdigest()
    total_records = inv_count + hazard_count

    # Write standalone checksum file
    with open(checksum_path, "w", encoding="utf-8") as f:
        f.write(f"{sha256_hex}  {archive_filename}\n")

    # Write manifest.json
    manifest_data = {
        "dataset_version": "v1.0",
        "generated_at": now_utc.isoformat(),
        "schema_version": "1.0",
        "record_count": total_records,
        "consenting_investigations_count": inv_count,
        "hazard_events_count": hazard_count,
        "archive_filename": archive_filename,
        "checksum": sha256_hex,
        "archive_size_bytes": archive_path.stat().st_size,
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

    # 3. Upload export files to the storage backend
    storage_backend = get_backup_storage()
    await storage_backend.upload(archive_path, archive_filename)
    await storage_backend.upload(checksum_path, f"{archive_filename}.sha256")
    await storage_backend.upload(manifest_path, "manifest.json")

    duration_ms = round((time.monotonic() - start_time) * 1000, 2)
    _log.info(
        "dataset_export.job.completed",
        duration_ms=duration_ms,
        record_count=total_records,
        archive_path=str(archive_path),
        checksum=sha256_hex,
    )

    return manifest_data


def run_dataset_export_job(*args: Any, **kwargs: Any) -> None:
    """RQ synchronous worker entry point."""
    asyncio.run(_async_run_dataset_export())


__all__ = ["run_dataset_export_job"]
