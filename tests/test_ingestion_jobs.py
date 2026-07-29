"""Integration tests for worker ingestion jobs, deduplication, and scheduler idempotency."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ingestion.scheduled.schemas import HazardEventRecord
from workers.jobs.ingestion_jobs import _async_run_ingestion_job
from workers.scheduler import is_job_already_scheduled


@pytest.mark.asyncio
class TestIngestionJobs:
    """Integration tests for ingestion worker job execution and persistence logic."""

    async def test_ingestion_job_feature_flag_disabled(self) -> None:
        """Verify ingestion job skips execution when feature flag is disabled."""
        with patch("workers.jobs.ingestion_jobs.get_settings") as mock_settings:
            mock_settings.return_value.enable_usgs_ingestion = False

            result = await _async_run_ingestion_job("usgs")
            assert result["status"] == "disabled"
            assert result["records_inserted"] == 0

    async def test_ingestion_job_deduplication_and_max_event_date_cursor_upsert(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Verify deduplication and max(event_date) cursor UPSERT."""
        trunc_stmt = text(
            "TRUNCATE TABLE hazard_relationships, hazard_events, ingestion_cursors CASCADE;"
        )
        await db_session.execute(trunc_stmt)
        await db_session.commit()

        d1 = datetime(2026, 7, 25, 10, 0, tzinfo=UTC)
        d2 = datetime(2026, 7, 25, 12, 0, tzinfo=UTC)  # Max date

        mock_records = [
            HazardEventRecord(
                source="usgs",
                external_id="us7000dedup1",
                event_type="earthquake",
                region_label="Tokyo",
                point=(35.6762, 139.6503),
                event_date=d1,
                details="Quake 1",
            ),
            HazardEventRecord(
                source="usgs",
                external_id="us7000dedup2",
                event_type="earthquake",
                region_label="Tokyo",
                point=(35.6762, 139.6503),
                event_date=d2,
                details="Quake 2",
            ),
        ]

        target_factory = "workers.jobs.ingestion_jobs.db_session.AsyncSessionLocal"
        target_fetch = "workers.jobs.ingestion_jobs.fetch_recent_usgs_events"
        target_settings = "workers.jobs.ingestion_jobs.get_settings"

        with (
            patch(target_factory) as mock_sess_factory,
            patch(target_fetch) as mock_fetch,
            patch(target_settings) as mock_settings,
        ):
            mock_sess_factory.return_value.__aenter__.return_value = db_session
            mock_settings.return_value.enable_usgs_ingestion = True
            mock_fetch.return_value = mock_records

            # Run 1: First insertion
            res1 = await _async_run_ingestion_job("usgs")
            assert res1["status"] == "success"
            assert res1["records_inserted"] == 2

            # Check cursor updated to max event date d2
            cursor_res = await db_session.execute(
                text("SELECT last_ingested_at FROM ingestion_cursors WHERE source = 'usgs';")
            )
            c_row = cursor_res.fetchone()
            assert c_row is not None
            assert c_row[0] == d2

            # Run 2: Duplicate insertion (same records)
            res2 = await _async_run_ingestion_job("usgs")
            assert res2["status"] == "success"
            # 0 new rows inserted due to ON CONFLICT DO NOTHING
            assert res2["records_inserted"] == 0


class TestSchedulerIdempotency:
    """Sync unit tests for RQ scheduler idempotency checks."""

    def test_scheduler_idempotency_detection(self) -> None:
        """Verify scheduler detects existing scheduled job to prevent duplicate registration."""
        mock_scheduler = MagicMock()

        mock_job1 = MagicMock()
        mock_job1.func_name = "workers.jobs.ingestion_jobs.run_ingestion_job"
        mock_job1.args = ["usgs"]

        mock_scheduler.get_jobs.return_value = [mock_job1]

        target = "workers.jobs.ingestion_jobs.run_ingestion_job"
        assert is_job_already_scheduled(mock_scheduler, target, "usgs") is True
        assert is_job_already_scheduled(mock_scheduler, target, "noaa") is False
