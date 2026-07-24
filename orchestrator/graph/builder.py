"""LangGraph execution graph builder."""

from __future__ import annotations

from datetime import UTC
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

import db.session as db_session
from cache.client import publish_event
from db.repository import InvestigationRepository
from logging_config import get_logger
from orchestrator.agents.air_quality.agent import run as run_air_quality
from orchestrator.agents.critic.agent import verify
from orchestrator.agents.critic.replan import build_replan_targets, should_replan
from orchestrator.agents.supervisor.classifier import classify_query_complexity
from orchestrator.agents.synthesis.agent import synthesize
from orchestrator.graph.fan_out_coordinator import FanOutCoordinator
from orchestrator.graph.state import TaskGraphState
from orchestrator.schemas.agent_io import AgentInput
from orchestrator.schemas.complexity import ComplexityTier
from orchestrator.schemas.events import (
    AgentCompletedData,
    AgentCompletedEvent,
    AgentStartedData,
    AgentStartedEvent,
    CriticFlagData,
    CriticFlagEvent,
    DoneData,
    DoneEvent,
    InvestigationEvent,
    PlanningData,
    PlanningEvent,
    ReplanningData,
    ReplanningEvent,
    SynthesizingEvent,
)
from orchestrator.schemas.synthesis import SynthesisOutput

_log = get_logger(__name__)


def _safe_publish_event(investigation_id: Any, event: InvestigationEvent) -> None:
    """Helper to publish event asynchronously and non-blockingly."""
    import asyncio

    async def _safe():
        try:
            await publish_event(investigation_id, event)
        except Exception as exc:
            _log.error(
                "graph.event_publish_failed",
                investigation_id=str(investigation_id),
                error=str(exc),
            )

    asyncio.create_task(_safe())


async def supervisor_node(state: TaskGraphState) -> dict[str, Any]:
    """Classify query complexity and route accordingly."""
    _log.info("graph.node.supervisor.started", investigation_id=str(state["investigation_id"]))
    _safe_publish_event(
        state["investigation_id"],
        PlanningEvent(data=PlanningData(status="planning")),
    )
    try:
        result = await classify_query_complexity(state["query"])
        return {
            "complexity_tier": result["tier"],
            "matched_domains": result["matched_domains"],
            "needs_simulation": result.get("needs_simulation", False),
        }
    except Exception as e:
        _log.error(
            "graph.node.supervisor.failed_fallback",
            query=state["query"],
            error=str(e),
            fallback_tier=ComplexityTier.MODERATE.value,
        )
        return {
            "complexity_tier": ComplexityTier.MODERATE,
            "matched_domains": [],
            "needs_simulation": False,
        }


def route_by_complexity(state: TaskGraphState) -> str:
    """Route conditional edge based on complexity tier."""
    tier = state.get("complexity_tier")
    matched = state.get("matched_domains", [])
    if tier == ComplexityTier.TRIVIAL and matched == ["air_quality"]:
        return "air_quality"
    return "fan_out"


async def air_quality_node(state: TaskGraphState) -> dict[str, Any]:
    """Execute the Air Quality agent node."""
    _log.info("graph.node.air_quality.started", investigation_id=str(state["investigation_id"]))
    from datetime import datetime

    _safe_publish_event(
        state["investigation_id"],
        AgentStartedEvent(
            data=AgentStartedData(
                agent="air_quality",
                at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            )
        ),
    )
    agent_input = AgentInput(
        investigation_id=state["investigation_id"],
        query=state["query"],
        region_hint=None,  # Parsed or extracted region
    )
    output = await run_air_quality(agent_input)
    _safe_publish_event(
        state["investigation_id"],
        AgentCompletedEvent(
            data=AgentCompletedData(
                agent="air_quality",
                evidence_count=len(output.evidence) if output.evidence else 0,
            )
        ),
    )
    return {"agent_outputs": [output]}


async def fan_out_node(state: TaskGraphState) -> dict[str, Any]:
    """Execute parallel FanOutCoordinator over matched domain agents."""
    _log.info("graph.node.fan_out.started", investigation_id=str(state["investigation_id"]))
    matched_domains = state.get("matched_domains", [])

    outputs = await FanOutCoordinator.run(
        domains=matched_domains,
        investigation_id=state["investigation_id"],
        query=state["query"],
        region_hint=None,
    )
    return {"agent_outputs": outputs}


def render_synthesis_output(synthesis_output: SynthesisOutput) -> str:
    """Render SynthesisOutput into a clean, human-readable markdown format."""
    lines = ["### Synthesized Answer\n"]
    for claim in synthesis_output.claims:
        lines.append(f"- **Claim:** {claim.text} (Confidence: {claim.confidence:.2f})")
        if claim.uncertainty_bounds:
            lines.append(f"  - *Uncertainty Bounds:* {claim.uncertainty_bounds}")
        if claim.assumptions:
            lines.append(f"  - *Assumptions:* {', '.join(claim.assumptions)}")
        for idx, ev in enumerate(claim.supporting_evidence, 1):
            lines.append(f"  - Citation [{idx}]: {ev.claim} (Source: {ev.source})")

    if synthesis_output.evidence_gaps:
        lines.append("\n### Identified Gaps")
        for gap in synthesis_output.evidence_gaps:
            lines.append(f"- No evidence gathered for domain: {gap}")

    return "\n".join(lines)


async def simulation_node(state: TaskGraphState) -> dict[str, Any]:
    """Execute the Simulation Agent node if prediction is required."""
    _log.info("graph.node.simulation.started", investigation_id=str(state["investigation_id"]))
    from datetime import datetime

    _safe_publish_event(
        state["investigation_id"],
        AgentStartedEvent(
            data=AgentStartedData(
                agent="simulation",
                at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            )
        ),
    )
    from orchestrator.agents.simulation.agent import run as run_simulation_agent

    agent_input = AgentInput(
        investigation_id=state["investigation_id"],
        query=state["query"],
        region_hint=None,
    )
    # Pass prior outputs
    output = await run_simulation_agent(agent_input, state.get("agent_outputs", []))
    _safe_publish_event(
        state["investigation_id"],
        AgentCompletedEvent(
            data=AgentCompletedData(
                agent="simulation",
                evidence_count=len(output.evidence) if output.evidence else 0,
            )
        ),
    )
    return {"agent_outputs": [output]}


def route_after_domain_agents(state: TaskGraphState) -> str:
    """Route after air_quality or fan_out based on needs_simulation flag."""
    if state.get("needs_simulation", False):
        return "simulation"
    return "synthesis"


async def synthesis_node(state: TaskGraphState) -> dict[str, Any]:
    """Execute the Synthesis Agent to merge findings and map citations."""
    _log.info("graph.node.synthesis.started", investigation_id=str(state["investigation_id"]))
    _safe_publish_event(
        state["investigation_id"],
        SynthesizingEvent(),
    )
    agent_outputs = state.get("agent_outputs", [])

    synthesis_output = await synthesize(agent_outputs)
    return {"synthesis_output": synthesis_output}


async def critic_node(state: TaskGraphState) -> dict[str, Any]:
    """Execute the Critic Agent to verify the synthesized claims."""
    _log.info("graph.node.critic.started", investigation_id=str(state["investigation_id"]))
    synthesis_output = state.get("synthesis_output")
    if not synthesis_output:
        return {"critic_flags": [], "final_answer": "No synthesized output to verify."}

    critic_flags = await verify(synthesis_output)

    # Emit critic flag events
    for flag in critic_flags:
        claim_confidence = 0.0
        if synthesis_output.claims:
            for claim in synthesis_output.claims:
                if claim.text == flag.claim_text:
                    claim_confidence = claim.confidence
                    break
        _safe_publish_event(
            state["investigation_id"],
            CriticFlagEvent(
                data=CriticFlagData(
                    claim=flag.claim_text,
                    confidence=claim_confidence,
                    reason=flag.flagged_reason,
                )
            ),
        )

    final_answer = render_synthesis_output(synthesis_output)
    return {
        "critic_flags": critic_flags,
        "final_answer": final_answer,
    }


def route_after_critic(state: TaskGraphState) -> str:
    """Route after critic verification: loop back to replan or proceed to finalize."""
    replan_count = state.get("replan_count", 0)
    critic_flags = state.get("critic_flags", [])
    if should_replan(critic_flags=critic_flags, replan_count=replan_count):
        return "replan"
    return "finalize"


async def replan_node(state: TaskGraphState) -> dict[str, Any]:
    """Execute a targeted replan pass over flagged domain agents."""
    replan_count = state.get("replan_count", 0) + 1
    critic_flags = state.get("critic_flags", [])
    high_flags = [f for f in critic_flags if f.severity == "high"]
    trigger_reason = (
        high_flags[0].flagged_reason
        if high_flags
        else (critic_flags[0].flagged_reason if critic_flags else "Critic verification flag")
    )

    matched_domains = state.get("matched_domains", [])
    targets = build_replan_targets(critic_flags, fallback_domains=matched_domains)

    _log.info(
        "graph.node.replan.started",
        investigation_id=str(state["investigation_id"]),
        cycle_number=replan_count,
        targeted_domains=targets,
        trigger_reason=trigger_reason,
    )

    _safe_publish_event(
        state["investigation_id"],
        ReplanningEvent(
            data=ReplanningData(
                cycle_number=replan_count,
                targeted_domains=targets,
                trigger_reason=trigger_reason,
            )
        ),
    )

    outputs = await FanOutCoordinator.run(
        domains=targets,
        investigation_id=state["investigation_id"],
        query=state["query"],
        region_hint=None,
    )

    return {
        "replan_count": replan_count,
        "agent_outputs": outputs,
    }


async def finalize_node(state: TaskGraphState) -> dict[str, Any]:
    """Finalize investigation, update database, emit done event, handle conflicts."""
    _log.info("graph.node.finalize.started", investigation_id=str(state["investigation_id"]))
    synthesis_output = state.get("synthesis_output")
    final_answer = state.get("final_answer") or (
        render_synthesis_output(synthesis_output) if synthesis_output else "No synthesis output."
    )
    critic_flags = state.get("critic_flags", [])
    replan_count = state.get("replan_count", 0)

    # If replan cap is reached with unresolved high-severity flags, append explicit conflict note
    has_unresolved_high = any(f.severity == "high" for f in critic_flags)
    if replan_count >= 2 and has_unresolved_high:
        final_answer += "\n\nUnresolved conflicting evidence."

    # Compute overall average confidence
    if synthesis_output and synthesis_output.claims:
        avg_confidence = sum(c.confidence for c in synthesis_output.claims) / len(
            synthesis_output.claims
        )
    else:
        avg_confidence = 0.0

    tier = state.get("complexity_tier")

    if isinstance(tier, ComplexityTier):
        tier_val = tier.value
    elif isinstance(tier, str):
        tier_val = tier
    else:
        tier_val = ComplexityTier.TRIVIAL.value

    nodes_executed = ["supervisor"]
    matched = state.get("matched_domains", [])
    if state.get("complexity_tier") == ComplexityTier.TRIVIAL and matched == ["air_quality"]:
        nodes_executed.append("air_quality")
    else:
        nodes_executed.append("fan_out")
    if state.get("needs_simulation", False):
        nodes_executed.append("simulation")
    nodes_executed.extend(["synthesis", "critic"])
    if replan_count > 0:
        nodes_executed.append("replan")
    nodes_executed.append("finalize")

    evidence_count = sum(len(out.evidence) for out in state.get("agent_outputs", []))

    trace = {
        "nodes_executed": nodes_executed,
        "evidence_count": evidence_count,
        "replan_count": replan_count,
        "critic_flags": [
            {
                "claim_text": flag.claim_text,
                "flagged_reason": flag.flagged_reason,
                "severity": flag.severity,
            }
            for flag in critic_flags
        ],
    }

    if db_session.AsyncSessionLocal is None:
        raise RuntimeError("Database session factory is not initialised.")

    async with db_session.AsyncSessionLocal() as session:
        await InvestigationRepository.update_investigation_status(
            session=session,
            investigation_id=state["investigation_id"],
            status="complete",
            complexity_tier=tier_val,
            answer=final_answer,
            confidence=avg_confidence,
            execution_trace=trace,
        )

    _safe_publish_event(
        state["investigation_id"],
        DoneEvent(
            data=DoneData(
                investigation_id=state["investigation_id"],
                status="complete",
            )
        ),
    )

    return {"final_answer": final_answer}


def build_graph(checkpointer: BaseCheckpointSaver) -> CompiledStateGraph:
    """Build and compile the orchestrator LangGraph skeleton."""
    workflow = StateGraph(TaskGraphState)

    # Add Nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("air_quality", air_quality_node)
    workflow.add_node("fan_out", fan_out_node)
    workflow.add_node("simulation", simulation_node)
    workflow.add_node("synthesis", synthesis_node)
    workflow.add_node("critic", critic_node)
    workflow.add_node("replan", replan_node)
    workflow.add_node("finalize", finalize_node)

    # Add Edges
    workflow.add_edge(START, "supervisor")

    # Conditional edge from supervisor to air_quality or fan_out
    workflow.add_conditional_edges(
        "supervisor",
        route_by_complexity,
        {
            "air_quality": "air_quality",
            "fan_out": "fan_out",
        },
    )

    # Conditional edge after air_quality to either simulation or synthesis
    workflow.add_conditional_edges(
        "air_quality",
        route_after_domain_agents,
        {
            "simulation": "simulation",
            "synthesis": "synthesis",
        },
    )

    # Conditional edge after fan_out to either simulation or synthesis
    workflow.add_conditional_edges(
        "fan_out",
        route_after_domain_agents,
        {
            "simulation": "simulation",
            "synthesis": "synthesis",
        },
    )

    workflow.add_edge("simulation", "synthesis")
    workflow.add_edge("synthesis", "critic")

    # Conditional edge after critic to replan or finalize
    workflow.add_conditional_edges(
        "critic",
        route_after_critic,
        {
            "replan": "replan",
            "finalize": "finalize",
        },
    )

    workflow.add_edge("replan", "synthesis")
    workflow.add_edge("finalize", END)

    return workflow.compile(checkpointer=checkpointer)
