"""Unit tests for Stage A — Collaboration Infrastructure (Phase 5 Milestone 4)."""

from __future__ import annotations

import asyncio

import pytest
from pydantic import ValidationError

from config.settings import Settings
from orchestrator.agents.base import BaseDomainAgent
from orchestrator.graph.collaboration_bus import CollaborationBus
from orchestrator.graph.fan_out_coordinator import FanOutCoordinator
from orchestrator.schemas.agent_io import AgentInput, AgentOutput, Evidence
from orchestrator.schemas.collaboration import CollaborationMessage
from orchestrator.schemas.uncertainty import UncertaintyEstimate


def test_collaboration_message_schema_and_immutability() -> None:
    """Verifies CollaborationMessage fields and frozen immutability."""
    unc = UncertaintyEstimate.from_point_estimate(0.85, source="well_supported")
    msg = CollaborationMessage(
        from_agent="seismic",
        finding_summary="Magnitude 6.5 earthquake in Tokyo",
        uncertainty=unc,
        suggested_refinement={"region_hint": "Tokyo, Japan"},
        round=0,
    )

    assert msg.from_agent == "seismic"
    assert msg.finding_summary == "Magnitude 6.5 earthquake in Tokyo"
    assert msg.uncertainty.point_estimate == 0.85
    assert msg.suggested_refinement == {"region_hint": "Tokyo, Japan"}
    assert msg.round == 0

    # Immutability check
    with pytest.raises(ValidationError):
        msg.finding_summary = "Modified summary"  # type: ignore[misc]


@pytest.mark.asyncio
async def test_collaboration_bus_passive_storage_and_filtering() -> None:
    """Verifies CollaborationBus stores messages and filters by requesting_agent and round."""
    bus = CollaborationBus(investigation_id="test-inv-123", max_rounds=2)
    unc = UncertaintyEstimate.from_point_estimate(0.9, source="well_supported")

    msg_seismic = CollaborationMessage(
        from_agent="seismic",
        finding_summary="Seismic activity detected",
        uncertainty=unc,
        round=0,
    )
    msg_ocean = CollaborationMessage(
        from_agent="ocean",
        finding_summary="Tsunami warning issued",
        uncertainty=unc,
        round=0,
    )
    msg_round1 = CollaborationMessage(
        from_agent="seismic",
        finding_summary="Aftershock detected",
        uncertainty=unc,
        round=1,
    )

    await bus.broadcast(msg_seismic)
    await bus.broadcast(msg_ocean)
    await bus.broadcast(msg_round1)

    # Ocean asks for peer findings (should exclude ocean's own message)
    ocean_peers = await bus.peer_findings(requesting_agent="ocean", since_round=0)
    assert len(ocean_peers) == 2
    assert all(m.from_agent != "ocean" for m in ocean_peers)

    # Filter since_round=1 (should return only round 1 message)
    round1_peers = await bus.peer_findings(requesting_agent="ocean", since_round=1)
    assert len(round1_peers) == 1
    assert round1_peers[0].finding_summary == "Aftershock detected"


@pytest.mark.asyncio
async def test_collaboration_bus_concurrent_broadcasts() -> None:
    """Verifies thread/task safety under concurrent broadcasts."""
    bus = CollaborationBus(investigation_id="concurrent-inv")
    unc = UncertaintyEstimate.from_point_estimate(0.8, source="well_supported")

    async def _broadcast_n(agent_name: str, count: int) -> None:
        for i in range(count):
            msg = CollaborationMessage(
                from_agent=agent_name,
                finding_summary=f"Finding {i}",
                uncertainty=unc,
                round=0,
            )
            await bus.broadcast(msg)

    # Run 5 concurrent broadcasting tasks
    tasks = [_broadcast_n(f"agent_{k}", 20) for k in range(5)]
    await asyncio.gather(*tasks)

    all_msgs = await bus.snapshot()
    assert len(all_msgs) == 100


def test_base_domain_agent_on_peer_finding_noop() -> None:
    """Verifies BaseDomainAgent.on_peer_finding defaults to returning None."""

    class TestAgent(BaseDomainAgent):
        pass

    agent = TestAgent()
    unc = UncertaintyEstimate.from_point_estimate(0.9, source="well_supported")
    msg = CollaborationMessage(
        from_agent="peer",
        finding_summary="Peer finding",
        uncertainty=unc,
    )

    result = agent.on_peer_finding(msg)
    assert result is None


@pytest.mark.asyncio
async def test_fan_out_coordinator_feature_flag_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifies coordinator passes no bus when feature flag is disabled (default)."""
    import uuid

    received_bus: CollaborationBus | None = None

    async def dummy_runner(
        agent_input: AgentInput, bus: CollaborationBus | None = None
    ) -> AgentOutput:
        nonlocal received_bus
        received_bus = bus
        return AgentOutput(agent_name="seismic", evidence=[], errors=[])

    monkeypatch.setattr(
        "orchestrator.graph.fan_out_coordinator.agent_registry.get",
        lambda domain: dummy_runner,
    )

    inv_id = uuid.uuid4()
    results = await FanOutCoordinator.run(
        domains=["seismic"],
        investigation_id=inv_id,
        query="Test query",
    )

    assert len(results) == 1
    assert received_bus is None


@pytest.mark.asyncio
async def test_fan_out_coordinator_feature_flag_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifies coordinator constructs and passes CollaborationBus when feature flag is enabled."""
    import uuid

    received_bus: CollaborationBus | None = None

    async def dummy_runner(
        agent_input: AgentInput, bus: CollaborationBus | None = None
    ) -> AgentOutput:
        nonlocal received_bus
        received_bus = bus
        return AgentOutput(agent_name="seismic", evidence=[], errors=[])

    # Override settings to enable collaboration
    test_settings = Settings(_env_file=None, ENABLE_AGENT_COLLABORATION=True)  # type: ignore[call-arg]
    monkeypatch.setattr(
        "orchestrator.graph.fan_out_coordinator.get_settings",
        lambda: test_settings,
    )
    monkeypatch.setattr(
        "orchestrator.graph.fan_out_coordinator.agent_registry.get",
        lambda domain: dummy_runner,
    )

    inv_id = uuid.uuid4()
    results = await FanOutCoordinator.run(
        domains=["seismic"],
        investigation_id=inv_id,
        query="Test query",
    )

    assert len(results) == 1
    assert received_bus is not None
    assert received_bus.investigation_id == str(inv_id)


@pytest.mark.asyncio
async def test_stage_b_seismic_ocean_collaboration_flow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stage B Integration: Seismic broadcast triggers Ocean agent refinement rerun."""
    import uuid

    ocean_runs: list[str | None] = []

    async def mock_seismic_runner(
        agent_input: AgentInput, bus: CollaborationBus | None = None
    ) -> AgentOutput:
        if bus is not None:
            unc = UncertaintyEstimate.from_point_estimate(0.9, source="well_supported")
            msg = CollaborationMessage(
                from_agent="seismic",
                finding_summary="Mag 6.0 earthquake in Tokyo",
                uncertainty=unc,
                suggested_refinement={"region_hint": "Tokyo"},
                round=0,
            )
            await bus.broadcast(msg)
        return AgentOutput(
            agent_name="seismic",
            evidence=[Evidence(source="seismic", claim="Quake 6.0", confidence=0.9)],
            errors=[],
        )

    async def mock_ocean_runner(
        agent_input: AgentInput, bus: CollaborationBus | None = None
    ) -> AgentOutput:
        ocean_runs.append(agent_input.region_hint)
        return AgentOutput(
            agent_name="ocean",
            evidence=[
                Evidence(
                    source="ocean",
                    claim=f"SST at {agent_input.region_hint or 'default'}",
                    confidence=0.85,
                )
            ],
            errors=[],
        )

    def mock_ocean_peer_hook(
        msg: CollaborationMessage, agent_input: AgentInput
    ) -> AgentInput | None:
        if msg.from_agent == "seismic" and msg.suggested_refinement:
            region = msg.suggested_refinement.get("region_hint")
            if region and agent_input.region_hint != region:
                return AgentInput(
                    investigation_id=agent_input.investigation_id,
                    query=agent_input.query,
                    region_hint=region,
                )
        return None

    mock_ocean_runner.on_peer_finding = mock_ocean_peer_hook  # type: ignore[attr-defined]

    registry_map = {
        "seismic": mock_seismic_runner,
        "ocean": mock_ocean_runner,
    }

    test_settings = Settings(_env_file=None, ENABLE_AGENT_COLLABORATION=True)  # type: ignore[call-arg]
    monkeypatch.setattr(
        "orchestrator.graph.fan_out_coordinator.get_settings",
        lambda: test_settings,
    )
    monkeypatch.setattr(
        "orchestrator.graph.fan_out_coordinator.agent_registry.get",
        lambda domain: registry_map[domain],
    )

    inv_id = uuid.uuid4()
    results = await FanOutCoordinator.run(
        domains=["seismic", "ocean"],
        investigation_id=inv_id,
        query="Tokyo natural hazards",
        region_hint=None,
    )

    assert len(results) == 2
    # Verify ocean runner was executed twice: initial run (None) and refined run ("Tokyo")
    assert ocean_runs == [None, "Tokyo"]
    ocean_out = next(r for r in results if r.agent_name == "ocean")
    assert "Tokyo" in ocean_out.evidence[0].claim


@pytest.mark.asyncio
async def test_stage_b_no_listener_safe_noop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stage B No-Listener: Seismic broadcasts when no listener agent exists."""
    import uuid

    async def mock_seismic_runner(
        agent_input: AgentInput, bus: CollaborationBus | None = None
    ) -> AgentOutput:
        if bus is not None:
            unc = UncertaintyEstimate.from_point_estimate(0.9, source="well_supported")
            await bus.broadcast(
                CollaborationMessage(
                    from_agent="seismic",
                    finding_summary="Quake in Pacific",
                    uncertainty=unc,
                    suggested_refinement={"region_hint": "Pacific"},
                    round=0,
                )
            )
        return AgentOutput(agent_name="seismic", evidence=[], errors=[])

    async def mock_atmosphere_runner(
        agent_input: AgentInput, bus: CollaborationBus | None = None
    ) -> AgentOutput:
        return AgentOutput(agent_name="atmosphere", evidence=[], errors=[])

    registry_map = {
        "seismic": mock_seismic_runner,
        "atmosphere": mock_atmosphere_runner,
    }

    test_settings = Settings(_env_file=None, ENABLE_AGENT_COLLABORATION=True)  # type: ignore[call-arg]
    monkeypatch.setattr(
        "orchestrator.graph.fan_out_coordinator.get_settings",
        lambda: test_settings,
    )
    monkeypatch.setattr(
        "orchestrator.graph.fan_out_coordinator.agent_registry.get",
        lambda domain: registry_map[domain],
    )

    inv_id = uuid.uuid4()
    results = await FanOutCoordinator.run(
        domains=["seismic", "atmosphere"],
        investigation_id=inv_id,
        query="Atmospheric query",
    )

    assert len(results) == 2


@pytest.mark.asyncio
async def test_stage_b_exception_isolation_in_peer_hook(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stage B Exception Isolation: Faulty peer hook raising Exception does not crash fan-out."""
    import uuid

    async def mock_seismic_runner(
        agent_input: AgentInput, bus: CollaborationBus | None = None
    ) -> AgentOutput:
        if bus is not None:
            unc = UncertaintyEstimate.from_point_estimate(0.9, source="well_supported")
            await bus.broadcast(
                CollaborationMessage(
                    from_agent="seismic",
                    finding_summary="Faulty hook test",
                    uncertainty=unc,
                    round=0,
                )
            )
        return AgentOutput(agent_name="seismic", evidence=[], errors=[])

    async def mock_faulty_runner(
        agent_input: AgentInput, bus: CollaborationBus | None = None
    ) -> AgentOutput:
        return AgentOutput(agent_name="faulty", evidence=[], errors=[])

    def broken_peer_hook(msg: CollaborationMessage, agent_input: AgentInput) -> AgentInput | None:
        raise ValueError("Simulated peer hook internal crash!")

    mock_faulty_runner.on_peer_finding = broken_peer_hook  # type: ignore[attr-defined]

    registry_map = {
        "seismic": mock_seismic_runner,
        "faulty": mock_faulty_runner,
    }

    test_settings = Settings(_env_file=None, ENABLE_AGENT_COLLABORATION=True)  # type: ignore[call-arg]
    monkeypatch.setattr(
        "orchestrator.graph.fan_out_coordinator.get_settings",
        lambda: test_settings,
    )
    monkeypatch.setattr(
        "orchestrator.graph.fan_out_coordinator.agent_registry.get",
        lambda domain: registry_map[domain],
    )

    inv_id = uuid.uuid4()
    results = await FanOutCoordinator.run(
        domains=["seismic", "faulty"],
        investigation_id=inv_id,
        query="Fault test",
    )

    assert len(results) == 2
    assert all(r.errors == [] for r in results)
