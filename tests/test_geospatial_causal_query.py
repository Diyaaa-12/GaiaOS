"""Unit and integration tests for PostGIS spatial proximity queries and index verification."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from geoalchemy2 import WKTElement
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from db.causal_repository import CausalChainRepository
from db.models.hazard_event import HazardEvent, HazardRelationship
from orchestrator.agents.causal_chain.agent import run as run_causal_chain_agent
from orchestrator.schemas.agent_io import AgentInput


@pytest.mark.asyncio
class TestGeospatialCausalQuery:
    """Verifies PostGIS ST_DWithin spatial matching and agent error paths."""

    async def test_spatial_radius_boundary_filtering(self, db_session: AsyncSession) -> None:
        """Verify ST_DWithin includes events inside 50km and excludes events outside 50km."""
        trunc_stmt = text("TRUNCATE TABLE hazard_relationships, hazard_events CASCADE;")
        await db_session.execute(trunc_stmt)

        # Point (0,0) origin
        # 1 degree longitude at equator ≈ 111,320 meters
        # 49.5 km ≈ 0.4446 degrees
        # 50.5 km ≈ 0.4536 degrees
        near_lon = 0.4446
        far_lon = 0.4536

        # Event A (inside 50km radius: ~49.5km)
        ev_a = HazardEvent(
            event_type="earthquake",
            region=WKTElement(f"POINT({near_lon} 0.0)", srid=4326),
            region_label="Near Location (49.5km)",
            event_date=datetime.now(UTC),
            details="Near quake",
        )
        ev_a_child = HazardEvent(
            event_type="tsunami",
            region=WKTElement(f"POINT({near_lon} 0.0)", srid=4326),
            region_label="Near Location (49.5km)",
            event_date=datetime.now(UTC),
            details="Near tsunami",
        )

        # Event B (outside 50km radius: ~50.5km)
        ev_b = HazardEvent(
            event_type="earthquake",
            region=WKTElement(f"POINT({far_lon} 0.0)", srid=4326),
            region_label="Far Location (50.5km)",
            event_date=datetime.now(UTC),
            details="Far quake",
        )
        ev_b_child = HazardEvent(
            event_type="landslide",
            region=WKTElement(f"POINT({far_lon} 0.0)", srid=4326),
            region_label="Far Location (50.5km)",
            event_date=datetime.now(UTC),
            details="Far landslide",
        )

        db_session.add_all([ev_a, ev_a_child, ev_b, ev_b_child])
        await db_session.flush()

        rel_a = HazardRelationship(
            parent_id=ev_a.id,
            child_id=ev_a_child.id,
            relationship_type="triggered",
            confidence=0.9,
        )
        rel_b = HazardRelationship(
            parent_id=ev_b.id,
            child_id=ev_b_child.id,
            relationship_type="triggered",
            confidence=0.8,
        )
        db_session.add_all([rel_a, rel_b])
        await db_session.commit()

        # Query centered at (0, 0) with a 50,000 meter search radius
        results = await CausalChainRepository.find_causal_chain(
            session=db_session,
            event_type="earthquake",
            point=(0.0, 0.0),  # (lat, lon)
            radius_meters=50000.0,
            max_depth=4,
        )

        # Assert Near Location event is included and Far Location event is excluded
        assert len(results) == 1
        assert "Near Location" in results[0].claim
        assert "tsunami" in results[0].extra_metadata["event_chain_path"]

    async def test_causal_chain_agent_geocoding_failure_surfaces_gap(self) -> None:
        """Verify that when geocoding fails, the agent surfaces an explicit error gap."""
        agent_input = AgentInput(
            investigation_id=uuid.uuid4(),
            query="earthquake in NonExistentAtlantis",
        )

        with patch("orchestrator.agents.causal_chain.agent.geocode_location") as mock_geocode:
            mock_err_msg = "Geocoding failed for unknown location: 'NonExistentAtlantis'"
            mock_geocode.side_effect = ValueError(mock_err_msg)

            output = await run_causal_chain_agent(agent_input)

            assert output.agent_name == "causal_chain"
            assert output.evidence == []
            assert output.errors == ["could not resolve region for causal analysis"]

    async def test_postgis_gist_index_verified(self, db_session: AsyncSession) -> None:
        """Verify that the PostGIS GIST spatial index exists on hazard_events table."""
        res = await db_session.execute(
            text(
                "SELECT indexname, indexdef FROM pg_indexes "
                "WHERE tablename = 'hazard_events' AND indexname = 'idx_hazard_events_region_gist';"
            )
        )
        row = res.fetchone()
        err_msg = "PostGIS GIST spatial index 'idx_hazard_events_region_gist' does not exist."
        assert row is not None, err_msg
        indexdef = str(row[1]).lower()
        assert "using gist" in indexdef, f"Index definition does not use GIST: {indexdef}"
