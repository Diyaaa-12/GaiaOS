"""Integration tests for PostgreSQL recursive CTE traversal, cycle prevention, and timeouts."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from db.causal_repository import CausalChainRepository
from db.models.hazard_event import HazardEvent, HazardRelationship


async def clean_and_seed_graph(
    session: AsyncSession,
    events_data: dict[str, dict],
    relations_data: list[tuple[str, str, str, float]],
) -> dict[str, HazardEvent]:
    """Helper to cleanly reset and seed a custom graph for isolated tests."""
    await session.execute(text("TRUNCATE TABLE hazard_relationships, hazard_events CASCADE;"))

    events = {}
    for key, data in events_data.items():
        ev = HazardEvent(
            event_type=data["event_type"],
            region=data["region"],
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

        # Retrieve chains starting with earthquake
        results = await CausalChainRepository.find_causal_chain(
            session=db_session,
            event_type="earthquake",
            region="Tokyo",
            max_depth=4,
        )

        # Expected chain: A -> B, A -> B -> C, A -> B -> C -> D
        # Result count should be 3
        assert len(results) == 3

        # Sort results by depth (via path length) to assert details
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
        assert results_sorted[1].confidence == 0.85  # min(0.85, 0.90)

        assert results_sorted[2].extra_metadata["depth"] == 4
        assert results_sorted[2].extra_metadata["event_chain_path"] == [
            "earthquake",
            "landslide",
            "river blockage",
            "flood",
        ]
        assert results_sorted[2].confidence == 0.85  # min(0.85, 0.90, 0.95)

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

        # Traversal with max_depth=2 should only return A -> B (depth 2)
        # and skip A -> B -> C (depth 3)
        results = await CausalChainRepository.find_causal_chain(
            session=db_session,
            event_type="earthquake",
            region="Tokyo",
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

        # Traversal should succeed and terminate, returning only the non-cyclic A -> B path
        results = await CausalChainRepository.find_causal_chain(
            session=db_session,
            event_type="earthquake",
            region="Tokyo",
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

        # Force a database transaction local statement_timeout to 1ms
        # This will trigger query cancel on postgres during execution
        with pytest.raises(TimeoutError) as exc_info:
            # We patch the statement timeout setter to 1ms inside the query block
            # To do this cleanly, we simulate it by setting SET LOCAL statement_timeout = 1
            # inside a subtransaction before calling find_causal_chain
            async with db_session.begin_nested():
                await db_session.execute(text("SET LOCAL statement_timeout = 1;"))
                # Running the query will trigger query cancel
                await CausalChainRepository.find_causal_chain(
                    session=db_session,
                    event_type="earthquake",
                    region="Tokyo",
                )

        assert "causal chain query exceeded time budget" in str(exc_info.value)

    async def test_disconnected_graph_handling(self, db_session: AsyncSession) -> None:
        """Verify that disconnected nodes or empty relations return empty results."""
        events_data = {
            "a": {"event_type": "earthquake", "region": "Tokyo"},
            "b": {"event_type": "landslide", "region": "Tokyo"},  # Disconnected
        }
        relations_data: list[tuple[str, str, str, float]] = []
        await clean_and_seed_graph(db_session, events_data, relations_data)

        results = await CausalChainRepository.find_causal_chain(
            session=db_session,
            event_type="earthquake",
            region="Tokyo",
        )

        assert len(results) == 0
