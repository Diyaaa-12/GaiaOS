"""Idempotent database seeder for historical hazard events and relationships."""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime

from sqlalchemy import func, select

from db.models.hazard_event import HazardEvent, HazardRelationship
from db.session import AsyncSessionLocal, dispose_engine, init_engine


async def seed_hazard_graph() -> None:
    """Seed connected historical hazard events and relationships idempotently."""
    print("Resolving database connection...")
    init_engine()

    if AsyncSessionLocal is None:
        print("Error: Database session factory is not initialised.")
        sys.exit(1)

    async with AsyncSessionLocal() as session:
        # Check if already seeded
        stmt = select(func.count()).select_from(HazardEvent)
        res = await session.execute(stmt)
        count = res.scalar()
        if count and count > 0:
            print("Hazard events already exist in the database. Skipping seeding.")
            await dispose_engine()
            return

        print("Seeding hazard events...")
        # 1. Seismic Chain events
        eq = HazardEvent(
            event_type="earthquake",
            region="Tokyo",
            event_date=datetime(2023, 9, 1, tzinfo=UTC),
            details="Magnitude 7.2 earthquake slip off the coast of Tokyo.",
        )
        ls = HazardEvent(
            event_type="landslide",
            region="Tokyo",
            event_date=datetime(2023, 9, 1, tzinfo=UTC),
            details="Hillside collapse triggers massive debris landslide.",
        )
        rb = HazardEvent(
            event_type="river blockage",
            region="Tokyo",
            event_date=datetime(2023, 9, 1, tzinfo=UTC),
            details="Tama River blockage caused by landslide debris accumulation.",
        )
        fl = HazardEvent(
            event_type="flood",
            region="Tokyo",
            event_date=datetime(2023, 9, 2, tzinfo=UTC),
            details="River overflow inundates low-lying residential regions.",
        )

        # 2. Marine Chain events
        hw = HazardEvent(
            event_type="marine heatwave",
            region="California",
            event_date=datetime(2024, 7, 10, tzinfo=UTC),
            details="Sea surface temperature anomalies exceed +3.0C in the Pacific.",
        )
        cb = HazardEvent(
            event_type="coral bleaching",
            region="California",
            event_date=datetime(2024, 7, 20, tzinfo=UTC),
            details="Severe thermal stress triggers widespread bleaching in reef structures.",
        )
        fm = HazardEvent(
            event_type="fish mortality",
            region="California",
            event_date=datetime(2024, 8, 1, tzinfo=UTC),
            details="High fish mortality rates linked to oxygen depletion and habitat loss.",
        )

        session.add_all([eq, ls, rb, fl, hw, cb, fm])
        # Flush to generate UUIDs
        await session.flush()

        print("Seeding hazard relationships...")
        # Seismic Chain relationships
        rel_eq_ls = HazardRelationship(
            parent_id=eq.id,
            child_id=ls.id,
            relationship_type="triggered",
            confidence=0.85,
        )
        rel_ls_rb = HazardRelationship(
            parent_id=ls.id,
            child_id=rb.id,
            relationship_type="preceded",
            confidence=0.90,
        )
        rel_rb_fl = HazardRelationship(
            parent_id=rb.id,
            child_id=fl.id,
            relationship_type="triggered",
            confidence=0.95,
        )

        # Marine Chain relationships
        rel_hw_cb = HazardRelationship(
            parent_id=hw.id,
            child_id=cb.id,
            relationship_type="triggered",
            confidence=0.92,
        )
        rel_cb_fm = HazardRelationship(
            parent_id=cb.id,
            child_id=fm.id,
            relationship_type="correlated_with",
            confidence=0.80,
        )

        session.add_all([rel_eq_ls, rel_ls_rb, rel_rb_fl, rel_hw_cb, rel_cb_fm])
        await session.commit()
        print("Causal-chain hazard graph seeded successfully!")

    await dispose_engine()


if __name__ == "__main__":
    asyncio.run(seed_hazard_graph())
