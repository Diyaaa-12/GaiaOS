"""Tests for mixed synthetic datasets containing planted signals and noise (Phase 7 Milestone 2)."""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.hazard_event import HazardEvent
from db.models.pattern_finding import PatternFinding
from workers.jobs.pattern_mining_job import execute_pattern_mining


@pytest.mark.asyncio
class TestPatternMiningMixedDataset:
    """Verifies true-positive signal detection and noise rejection on mixed datasets."""

    async def test_mixed_dataset_detects_planted_pattern_and_rejects_noise(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Seed a planted (earthquake -> ocean_anomaly) pattern plus background noise."""
        random.seed(123)
        base_time = datetime.now(UTC) - timedelta(days=40)

        # 1. Planted Pattern: 6 earthquake events followed by ocean_anomaly in "Pacific"
        for i in range(6):
            eq_date = base_time + timedelta(days=i * 5)
            eq_ev = HazardEvent(
                event_type="earthquake",
                region_label="Pacific",
                event_date=eq_date,
                details=f"Planted Earthquake {i}",
                source="planted_fixture",
            )
            oa_ev = HazardEvent(
                event_type="ocean_anomaly",
                region_label="Pacific",
                event_date=eq_date + timedelta(days=2),
                details=f"Planted Ocean Anomaly {i}",
                source="planted_fixture",
            )
            db_session.add(eq_ev)
            db_session.add(oa_ev)

        # 2. Add 20 random noise events in "Atlantic" and "Indian"
        for i in range(20):
            ev_type = random.choice(["wildfire", "flood", "storm"])
            reg = random.choice(["Atlantic", "Indian"])
            offset = random.randint(0, 35 * 86400)
            noise_ev = HazardEvent(
                event_type=ev_type,
                region_label=reg,
                event_date=base_time + timedelta(seconds=offset),
                details=f"Noise Event {i}",
                source="noise_fixture",
            )
            db_session.add(noise_ev)

        await db_session.commit()

        # Run pattern mining job
        res = await execute_pattern_mining(source_tag="test_mixed")
        assert res["accepted_findings"] >= 1

        # Query database to verify accepted pattern finding
        stmt = select(PatternFinding).where(PatternFinding.is_active.is_(True))
        db_res = await db_session.execute(stmt)
        findings = list(db_res.scalars().all())

        # Assert the planted pattern was found
        planted = next(
            (
                f
                for f in findings
                if f.source_event_type == "earthquake"
                and f.target_event_type == "ocean_anomaly"
                and f.region_label == "Pacific"
            ),
            None,
        )
        assert planted is not None
        assert planted.support_count == 6
        assert planted.lift > 1.5
        assert planted.statistical_confidence >= 0.70

        # Assert zero findings were generated for the noise event types/regions
        for f in findings:
            assert f.region_label != "Atlantic"
            assert f.region_label != "Indian"
