"""Worker jobs for automated historical hazard event ingestion."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime
from typing import Any

from sqlalchemy import text

import db.session as db_session
from config.settings import get_settings
from ingestion.scheduled.hazard_event_sources.copernicus_wildfire import (
    fetch_recent_copernicus_events,
)
from ingestion.scheduled.hazard_event_sources.era5_atmospheric import fetch_recent_era5_events
from ingestion.scheduled.hazard_event_sources.gdelt_events import fetch_recent_gdelt_events
from ingestion.scheduled.hazard_event_sources.noaa_historical import fetch_recent_noaa_events
from ingestion.scheduled.hazard_event_sources.usgs_historical import fetch_recent_usgs_events
from ingestion.scheduled.schemas import HazardEventRecord
from logging_config import configure_logging, get_logger
from metrics.collector import emit, persist_metric
from metrics.events import IngestionCompleted

_log = get_logger(__name__)


async def _async_run_ingestion_job(source: str) -> dict[str, Any]:
    """Internal async implementation of the scheduled ingestion worker job."""
    start_time = time.perf_counter()
    source_clean = source.strip().lower()
    settings = get_settings()

    # 1. Feature Flag Check
    if source_clean == "usgs" and not settings.enable_usgs_ingestion:
        _log.info("ingestion.job.disabled", source=source_clean)
        return {"status": "disabled", "source": source_clean, "records_inserted": 0}
    if source_clean == "noaa" and not settings.enable_noaa_ingestion:
        _log.info("ingestion.job.disabled", source=source_clean)
        return {"status": "disabled", "source": source_clean, "records_inserted": 0}
    if source_clean == "copernicus" and not settings.enable_copernicus_ingestion:
        _log.info("ingestion.job.disabled", source=source_clean)
        return {"status": "disabled", "source": source_clean, "records_inserted": 0}
    if source_clean == "era5" and not settings.enable_era5_ingestion:
        _log.info("ingestion.job.disabled", source=source_clean)
        return {"status": "disabled", "source": source_clean, "records_inserted": 0}
    if source_clean == "gdelt" and not settings.enable_gdelt_ingestion:
        _log.info("ingestion.job.disabled", source=source_clean)
        return {"status": "disabled", "source": source_clean, "records_inserted": 0}

    if db_session.AsyncSessionLocal is None:
        db_session.init_engine()
        if db_session.AsyncSessionLocal is None:
            raise RuntimeError("Database session factory is not initialised.")

    async with db_session.AsyncSessionLocal() as session:
        # 2. Get last cursor from PostgreSQL ingestion_cursors
        cursor_res = await session.execute(
            text("SELECT last_ingested_at FROM ingestion_cursors WHERE source = :source;"),
            {"source": source_clean},
        )
        cursor_row = cursor_res.fetchone()
        last_ingested_at: datetime | None = cursor_row[0] if cursor_row else None

        # 3. Fetch recent records from source
        records: list[HazardEventRecord] = []
        if source_clean == "usgs":
            records = await fetch_recent_usgs_events(since=last_ingested_at)
        elif source_clean == "noaa":
            records = await fetch_recent_noaa_events(since=last_ingested_at)
        elif source_clean == "copernicus":
            records = await fetch_recent_copernicus_events(since=last_ingested_at)
        elif source_clean == "era5":
            records = await fetch_recent_era5_events(since=last_ingested_at)
        elif source_clean == "gdelt":
            records = await fetch_recent_gdelt_events(since=last_ingested_at)
        else:
            raise ValueError(f"Unknown ingestion source: '{source}'")


        records_fetched = len(records)
        records_inserted = 0

        # 4. Insert new records with ON CONFLICT (source, external_id) DO NOTHING
        if records:
            insert_stmt = text("""
                INSERT INTO hazard_events (
                    id, event_type, region, region_label, event_date,
                    details, source, external_id, created_at
                )
                VALUES (
                    gen_random_uuid(), :event_type, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
                    :region_label, :event_date, :details, :source, :external_id, now()
                )
                ON CONFLICT (source, external_id) DO NOTHING;
            """)

            for rec in records:
                res = await session.execute(
                    insert_stmt,
                    {
                        "event_type": rec.event_type,
                        "lon": rec.point[1],
                        "lat": rec.point[0],
                        "region_label": rec.region_label,
                        "event_date": rec.event_date,
                        "details": rec.details,
                        "source": rec.source,
                        "external_id": rec.external_id,
                    },
                )
                rc = getattr(res, "rowcount", 0)
                if rc is not None and rc > 0:
                    records_inserted += 1

            # 5. Cursor advancement strictly to max(event_date) of ingested records via UPSERT
            max_event_date = max(rec.event_date for rec in records)
            upsert_cursor_stmt = text("""
                INSERT INTO ingestion_cursors (source, last_ingested_at, updated_at)
                VALUES (:source, :max_event_date, now())
                ON CONFLICT (source) DO UPDATE
                SET last_ingested_at = EXCLUDED.last_ingested_at,
                    updated_at = now();
            """)
            await session.execute(
                upsert_cursor_stmt,
                {"source": source_clean, "max_event_date": max_event_date},
            )

        await session.commit()

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        _log.info(
            "ingestion.job.completed",
            source=source_clean,
            records_fetched=records_fetched,
            records_inserted=records_inserted,
            duration_ms=duration_ms,
        )

        ingestion_event = IngestionCompleted(
            source=source_clean,
            records_fetched=records_fetched,
            records_inserted=records_inserted,
            duration_ms=duration_ms,
            success=True,
        )
        emit(ingestion_event)
        await persist_metric(session, ingestion_event)
        await session.commit()

        return {
            "status": "success",
            "source": source_clean,
            "records_fetched": records_fetched,
            "records_inserted": records_inserted,
            "duration_ms": duration_ms,
        }


def run_ingestion_job(source: str) -> dict[str, Any]:
    """RQ Worker entrypoint function for executing an ingestion job by source."""
    settings = get_settings()
    configure_logging(settings)
    return asyncio.run(_async_run_ingestion_job(source))
