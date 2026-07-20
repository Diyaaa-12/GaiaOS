"""LangGraph execution graph builder."""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

import db.session as db_session
from db.repository import InvestigationRepository
from logging_config import get_logger
from orchestrator.agents.air_quality.agent import run as run_air_quality
from orchestrator.agents.critic.agent import verify
from orchestrator.agents.supervisor.classifier import classify_query_complexity
from orchestrator.agents.synthesis.agent import synthesize
from orchestrator.graph.fan_out_coordinator import FanOutCoordinator
from orchestrator.graph.state import TaskGraphState
from orchestrator.schemas.agent_io import AgentInput
from orchestrator.schemas.complexity import ComplexityTier
from orchestrator.schemas.synthesis import SynthesisOutput

_log = get_logger(__name__)


async def supervisor_node(state: TaskGraphState) -> dict[str, Any]:
    """Classify query complexity and route accordingly."""
    _log.info("graph.node.supervisor.started", investigation_id=str(state["investigation_id"]))
    try:
        result = await classify_query_complexity(state["query"])
        return {
            "complexity_tier": result["tier"],
            "matched_domains": result["matched_domains"],
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
    agent_input = AgentInput(
        investigation_id=state["investigation_id"],
        query=state["query"],
        region_hint=None,  # Parsed or extracted region
    )
    output = await run_air_quality(agent_input)
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
        for idx, ev in enumerate(claim.supporting_evidence, 1):
            lines.append(f"  - Citation [{idx}]: {ev.claim} (Source: {ev.source})")

    if synthesis_output.evidence_gaps:
        lines.append("\n### Identified Gaps")
        for gap in synthesis_output.evidence_gaps:
            lines.append(f"- No evidence gathered for domain: {gap}")

    return "\n".join(lines)


async def synthesis_node(state: TaskGraphState) -> dict[str, Any]:
    """Execute the Synthesis Agent to merge findings and map citations."""
    _log.info("graph.node.synthesis.started", investigation_id=str(state["investigation_id"]))
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

    # Render final answer text
    final_answer = render_synthesis_output(synthesis_output)

    # Compute overall average confidence
    if synthesis_output.claims:
        avg_confidence = sum(c.confidence for c in synthesis_output.claims) / len(
            synthesis_output.claims
        )
    else:
        avg_confidence = 0.0

    # Build execution trace
    tier_val = (
        state.get("complexity_tier").value
        if state.get("complexity_tier")
        else ComplexityTier.TRIVIAL.value
    )

    nodes_executed = ["supervisor"]
    matched = state.get("matched_domains", [])
    if state.get("complexity_tier") == ComplexityTier.TRIVIAL and matched == ["air_quality"]:
        nodes_executed.append("air_quality")
    else:
        nodes_executed.append("fan_out")
    nodes_executed.extend(["synthesis", "critic"])

    evidence_count = sum(len(out.evidence) for out in state.get("agent_outputs", []))

    trace = {
        "nodes_executed": nodes_executed,
        "evidence_count": evidence_count,
        "critic_flags": [
            {
                "claim_text": flag.claim_text,
                "flagged_reason": flag.flagged_reason,
                "severity": flag.severity,
            }
            for flag in critic_flags
        ],
    }

    # Save to database
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

    return {
        "critic_flags": critic_flags,
        "final_answer": final_answer,
    }


def build_graph(checkpointer: BaseCheckpointSaver) -> CompiledStateGraph:
    """Build and compile the orchestrator LangGraph skeleton."""
    workflow = StateGraph(TaskGraphState)

    # Add Nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("air_quality", air_quality_node)
    workflow.add_node("fan_out", fan_out_node)
    workflow.add_node("synthesis", synthesis_node)
    workflow.add_node("critic", critic_node)

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

    workflow.add_edge("air_quality", "synthesis")
    workflow.add_edge("fan_out", "synthesis")
    workflow.add_edge("synthesis", "critic")
    workflow.add_edge("critic", END)

    return workflow.compile(checkpointer=checkpointer)
