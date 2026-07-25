"""Integration tests for PostgreSQL recursive CTE traversal, cycle prevention, and timeouts."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from geoalchemy2 import WKTElement
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from db.causal_repository import CausalChainRepository
from db.models.hazard_event import HazardEvent, HazardRelationship

TOKYO_POINT = (35.6762, 139.6503)  # (lat, lon)


async def clean_and_seed_graph(
    session: AsyncSession,
    events_data: dict[str, dict],
    relations_data: list[tuple[str, str, str, float]],
) -> dict[str, HazardEvent]:
    """Helper to cleanly reset and seed a custom graph for isolated tests."""
    await session.execute(text("TRUNCATE TABLE hazard_relationships, hazard_events CASCADE;"))

    events = {}
    for key, data in events_data.items():
        lat = data.get("lat", 35.6762)
        lon = data.get("lon", 139.6503)
        region_name = data.get("region", "Tokyo")
        ev = HazardEvent(
            event_type=data["event_type"],
            region=WKTElement(f"POINT({lon} {lat})", srid=4326),
            region_label=region_name,
            event_date=data.get("event_date", datetime.now(UTC)),
            details=data.get("details"),
        )
        session.add(ev)
        events[key] = ev

    await session.flush()

    for p_key, c_key, r_type, conf in relations_data:
        rel = HazardRelationship(
            parent_id=events[p_key].id,
            child_id=events[c_key].id,
            relationship_type=r_type,
            confidence=conf,
        )
        session.add(rel)

    await session.commit()
    return events


class TestRecursiveCTE:
    """Verifies recursive traversal logic, cycle prevention, and depth limits."""

    async def test_multi_hop_chain_traversal(self, db_session: AsyncSession) -> None:
        """Verify successful traversal of a 3-hop chain (A -> B -> C -> D)."""
        events_data = {
            "a": {"event_type": "earthquake", "region": "Tokyo", "details": "Initial quake"},
            "b": {"event_type": "landslide", "region": "Tokyo", "details": "Landslide collapse"},
            "c": {"event_type": "river blockage", "region": "Tokyo", "details": "Tama river block"},
            "d": {"event_type": "flood", "region": "Tokyo", "details": "Low-lying flooding"},
        }
        relations_data = [
            ("a", "b", "triggered", 0.85),
            ("b", "c", "preceded", 0.90),
            ("c", "d", "triggered", 0.95),
        ]
        await clean_and_seed_graph(db_session, events_data, relations_data)

        # Retrieve chains starting with earthquake near Tokyo
        results = await CausalChainRepository.find_causal_chain(
            session=db_session,
            event_type="earthquake",
            point=TOKYO_POINT,
            radius_meters=50000.0,
            max_depth=4,
        )

        assert len(results) == 3

        results_sorted = sorted(results, key=lambda x: x.extra_metadata["depth"])

        assert results_sorted[0].extra_metadata["depth"] == 2
        assert results_sorted[0].extra_metadata["event_chain_path"] == ["earthquake", "landslide"]
        assert results_sorted[0].confidence == 0.85

        assert results_sorted[1].extra_metadata["depth"] == 3
        assert results_sorted[1].extra_metadata["event_chain_path"] == [
            "earthquake",
            "landslide",
            "river blockage",
        ]
        assert results_sorted[1].confidence == 0.85

        assert results_sorted[2].extra_metadata["depth"] == 4
        assert results_sorted[2].extra_metadata["event_chain_path"] == [
            "earthquake",
            "landslide",
            "river blockage",
            "flood",
        ]
        assert results_sorted[2].confidence == 0.85

    async def test_depth_limiting_enforcement(self, db_session: AsyncSession) -> None:
        """Verify that traversal respects the max_depth limit and excludes deeper nodes."""
        events_data = {
            "a": {"event_type": "earthquake", "region": "Tokyo"},
            "b": {"event_type": "landslide", "region": "Tokyo"},
            "c": {"event_type": "flood", "region": "Tokyo"},
        }
        relations_data = [
            ("a", "b", "triggered", 0.90),
            ("b", "c", "triggered", 0.80),
        ]
        await clean_and_seed_graph(db_session, events_data, relations_data)

        results = await CausalChainRepository.find_causal_chain(
            session=db_session,
            event_type="earthquake",
            point=TOKYO_POINT,
            radius_meters=50000.0,
            max_depth=2,
        )

        assert len(results) == 1
        assert results[0].extra_metadata["event_chain_path"] == ["earthquake", "landslide"]

    async def test_cycle_protection_termination(self, db_session: AsyncSession) -> None:
        """Verify that a cyclic relationship (A -> B -> A) terminates without infinite recursion."""
        events_data = {
            "a": {"event_type": "earthquake", "region": "Tokyo"},
            "b": {"event_type": "landslide", "region": "Tokyo"},
        }
        relations_data = [
            ("a", "b", "triggered", 0.90),
            ("b", "a", "triggered", 0.80),
        ]
        await clean_and_seed_graph(db_session, events_data, relations_data)

        results = await CausalChainRepository.find_causal_chain(
            session=db_session,
            event_type="earthquake",
            point=TOKYO_POINT,
            radius_meters=50000.0,
            max_depth=5,
        )

        assert len(results) == 1
        assert results[0].extra_metadata["event_chain_path"] == ["earthquake", "landslide"]

    async def test_statement_timeout_handling(self, db_session: AsyncSession) -> None:
        """Verify that an extremely short statement timeout triggers a TimeoutError gracefully."""
        events_data = {
            "a": {"event_type": "earthquake", "region": "Tokyo"},
            "b": {"event_type": "landslide", "region": "Tokyo"},
        }
        relations_data = [
            ("a", "b", "triggered", 0.90),
        ]
        await clean_and_seed_graph(db_session, events_data, relations_data)

        with pytest.raises(TimeoutError) as exc_info:
            async with db_session.begin_nested():
                await CausalChainRepository.find_causal_chain(
                    session=db_session,
                    event_type="earthquake",
                    point=TOKYO_POINT,
                    radius_meters=50000.0,
                    statement_timeout_ms=1,
                )

        assert "causal chain query exceeded time budget" in str(exc_info.value)

    async def test_disconnected_graph_handling(self, db_session: AsyncSession) -> None:
        """Verify that disconnected nodes or empty relations return empty results."""
        events_data = {
            "a": {"event_type": "earthquake", "region": "Tokyo"},
            "b": {"event_type": "landslide", "region": "Tokyo"},
        }
        relations_data: list[tuple[str, str, str, float]] = []
        await clean_and_seed_graph(db_session, events_data, relations_data)

        results = await CausalChainRepository.find_causal_chain(
            session=db_session,
            event_type="earthquake",
            point=TOKYO_POINT,
            radius_meters=50000.0,
        )

        assert len(results) == 0
