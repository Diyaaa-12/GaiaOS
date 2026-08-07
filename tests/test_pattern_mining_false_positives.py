"""Regression tests for pattern mining false-positive rejection (Phase 7 Milestone 2)."""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.hazard_event import HazardEvent
from workers.jobs.pattern_mining_job import execute_pattern_mining


@pytest.mark.asyncio
class TestPatternMiningFalsePositives:
    """Proves random/shuffled datasets produce no false-positive pattern findings."""

    async def test_random_uniform_dataset_produces_no_false_positives(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Seed 50 randomly distributed hazard events without temporal correlation."""
        random.seed(42)  # Deterministic seed

        event_types = ["earthquake", "flood", "wildfire", "storm", "volcano"]
        regions = ["RegionA", "RegionB", "RegionC"]
        base_time = datetime.now(UTC) - timedelta(days=30)

        # Generate 50 independent random events across 30 days
        for i in range(50):
            ev_type = random.choice(event_types)
            reg = random.choice(regions)
            offset_seconds = random.randint(0, 30 * 86400)
            ev_date = base_time + timedelta(seconds=offset_seconds)

            ev = HazardEvent(
                event_type=ev_type,
                region_label=reg,
                event_date=ev_date,
                details=f"Random noise event {i}",
                source="test_random_fixture",
            )
            db_session.add(ev)

        await db_session.commit()

        # Run pattern mining job logic
        res = await execute_pattern_mining(source_tag="test_false_positive")
        assert res["events_scanned"] >= 50
        # Assert 0 false positive pattern findings are accepted
        assert res["accepted_findings"] == 0
