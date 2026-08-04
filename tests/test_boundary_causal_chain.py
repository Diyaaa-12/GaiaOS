"""Integration tests for boundary-mode causal chain queries and radius fallback."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from db.causal_repository import CausalChainRepository
from orchestrator.agents.causal_chain import agent as causal_chain_agent
from orchestrator.schemas.agent_io import AgentInput


@pytest.mark.asyncio
async def test_boundary_mode_causal_chain_query(db_session: AsyncSession) -> None:
    """Test ST_Within recursive causal chain query against a seeded administrative boundary."""
    # 1. Create a boundary polygon for test region
    boundary_id = uuid.uuid4()
    osm_id = f"relation/{uuid.uuid4().hex[:8]}"
    await db_session.execute(
        text("""
            INSERT INTO administrative_boundaries (id, osm_id, name, admin_level, geom, created_at)
            VALUES (
                :id,
                :osm_id,
                'Test Region',
                4,
                ST_Multi(ST_SetSRID(ST_MakeEnvelope(10.0, 10.0, 20.0, 20.0), 4326)),
                NOW()
            );
        """),
        {"id": boundary_id, "osm_id": osm_id},
    )

    # 2. Insert parent event inside boundary and child event
    parent_id = uuid.uuid4()
    child_id = uuid.uuid4()

    await db_session.execute(
        text("""
            INSERT INTO hazard_events (id, event_type, region, region_label, details, created_at)
            VALUES (
                :id,
                'wildfire',
                ST_SetSRID(ST_MakePoint(15.0, 15.0), 4326),
                'Test Region',
                'Wildfire inside boundary',
                NOW()
            );
        """),
        {"id": parent_id},
    )

    await db_session.execute(
        text("""
            INSERT INTO hazard_events (id, event_type, region, region_label, details, created_at)
            VALUES (
                :id,
                'earthquake',
                ST_SetSRID(ST_MakePoint(16.0, 16.0), 4326),
                'Test Region',
                'Cascading earthquake inside boundary',
                NOW()
            );
        """),
        {"id": child_id},
    )

    await db_session.execute(
        text("""
            INSERT INTO hazard_relationships
                (id, parent_id, child_id, relationship_type, confidence, created_at)
            VALUES (
                :id,
                :parent_id,
                :child_id,
                'triggers',
                0.85,
                NOW()
            );
        """),
        {
            "id": uuid.uuid4(),
            "parent_id": parent_id,
            "child_id": child_id,
        },
    )

    await db_session.commit()

    # 3. Query causal chain within boundary
    evidence = await CausalChainRepository.find_causal_chain_within_boundary(
        session=db_session,
        event_type="wildfire",
        boundary_id=boundary_id,
        max_depth=4,
    )

    assert len(evidence) >= 1
    assert "wildfire -> earthquake" in evidence[0].claim


@pytest.mark.asyncio
async def test_causal_chain_agent_fallback_when_boundary_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that setting ENABLE_BOUNDARY_REASONING=false forces fallback to radius mode."""
    monkeypatch.setenv("ENABLE_BOUNDARY_REASONING", "false")

    agent_input = AgentInput(
        investigation_id=uuid.uuid4(),
        query="What historical earthquakes occurred near Paris?",
    )
    output = await causal_chain_agent.run(agent_input)

    assert output.agent_name == "causal_chain"
    assert isinstance(output.evidence, list)
