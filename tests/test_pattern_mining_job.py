"""Integration tests for background pattern mining job (Phase 7 Milestone 2)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.hazard_event import HazardEvent
from db.models.pattern_finding import PatternFinding
from db.repository import PatternFindingRepository
from workers.jobs.pattern_mining_job import run_pattern_mining_job


@pytest.mark.asyncio
class TestPatternMiningJobIntegration:
    """Integration test suite for pattern mining job and repository versioning."""

    async def test_repository_save_pattern_version(
        self,
        db_session: AsyncSession,
    ) -> None:
        """save_pattern_version deactivates previous version and increments version counter."""
        hash_key = "test_hash_1234567890abcdef"
        mined_time = datetime.now(UTC)

        # 1. First version
        f1 = await PatternFindingRepository.save_pattern_version(
            session=db_session,
            pattern_hash=hash_key,
            source_event_type="earthquake",
            target_event_type="tsunami",
            region_label="Japan",
            time_window_days=7,
            support_count=5,
            total_source_events=5,
            total_target_events=5,
            observed_rate=1.0,
            baseline_rate=0.2,
            lift=5.0,
            statistical_confidence=0.75,
            uncertainty={
                "point_estimate": 0.75,
                "lower_bound": 0.67,
                "upper_bound": 0.83,
                "source": "well_supported",
            },
            supporting_event_ids=["id1", "id2"],
            description="Initial pattern finding",
            mined_at=mined_time,
        )
        await db_session.commit()
        assert f1.version == 1
        assert f1.is_active is True

        # 2. Second version
        f2 = await PatternFindingRepository.save_pattern_version(
            session=db_session,
            pattern_hash=hash_key,
            source_event_type="earthquake",
            target_event_type="tsunami",
            region_label="Japan",
            time_window_days=7,
            support_count=8,
            total_source_events=8,
            total_target_events=8,
            observed_rate=1.0,
            baseline_rate=0.2,
            lift=5.0,
            statistical_confidence=0.82,
            uncertainty={
                "point_estimate": 0.82,
                "lower_bound": 0.74,
                "upper_bound": 0.90,
                "source": "well_supported",
            },
            supporting_event_ids=["id1", "id2", "id3"],
            description="Updated pattern finding",
            mined_at=mined_time + timedelta(hours=24),
        )
        await db_session.commit()
        assert f2.version == 2
        assert f2.is_active is True

        # Verify f1 was deactivated
        await db_session.refresh(f1)
        assert f1.is_active is False

        # Query all versions
        stmt = (
            select(PatternFinding)
            .where(PatternFinding.pattern_hash == hash_key)
            .order_by(PatternFinding.version.asc())
        )
        res = await db_session.execute(stmt)
        all_versions = list(res.scalars().all())
        assert len(all_versions) == 2

    async def test_run_pattern_mining_job_entrypoint(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Synchronous wrapper run_pattern_mining_job executes without throwing."""
        # Seed minimal event
        ev = HazardEvent(
            event_type="seismic",
            region_label="Global",
            event_date=datetime.now(UTC),
            details="Test event",
        )
        db_session.add(ev)
        await db_session.commit()

        res = run_pattern_mining_job(source="test_entrypoint")
        assert "events_scanned" in res
        assert "candidate_pairs" in res
        assert "accepted_findings" in res
