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
from orchestrator.agents.supervisor.planner import classify_query
from orchestrator.graph.state import TaskGraphState
from orchestrator.schemas.agent_io import AgentInput
from orchestrator.schemas.complexity import ComplexityTier

_log = get_logger(__name__)


async def supervisor_node(state: TaskGraphState) -> dict[str, Any]:
    """Classify query complexity and route accordingly."""
    _log.info("graph.node.supervisor.started", investigation_id=str(state["investigation_id"]))
    tier = await classify_query(state["query"])
    return {"complexity_tier": tier}


def route_by_complexity(state: TaskGraphState) -> str:
    """Route conditional edge based on complexity tier."""
    # In Milestone 2, all paths route to the air_quality agent
    return "air_quality"


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


async def synthesis_node(state: TaskGraphState) -> dict[str, Any]:
    """Synthesize final answer and save state to episodic log database."""
    _log.info("graph.node.synthesis.started", investigation_id=str(state["investigation_id"]))

    outputs = state.get("agent_outputs", [])

    # Simple Synthesis Stub for Milestone 2
    claims = []
    errors = []
    for out in outputs:
        errors.extend(out.errors)
        for ev in out.evidence:
            claims.append(
                f"- {ev.claim} (Source: {ev.source}, Confidence: {ev.confidence:.2f})"
            )

    if errors:
        err_str = "; ".join(errors)
        claims.append(f"Errors encountered: {err_str}")

    if not claims:
        final_answer = "No evidence gathered for the query."
    else:
        claims_str = "\n".join(claims)
        final_answer = f"Investigation Report:\n{claims_str}"

    tier_val = (
        state.get("complexity_tier").value
        if state.get("complexity_tier")
        else ComplexityTier.TRIVIAL.value
    )

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
            confidence=1.0 if claims else 0.0,
            execution_trace={
                "nodes_executed": ["supervisor", "air_quality", "synthesis"],
                "evidence_count": len(claims),
            },
        )

    return {"final_answer": final_answer}


def build_graph(checkpointer: BaseCheckpointSaver) -> CompiledStateGraph:
    """Build and compile the orchestrator LangGraph skeleton."""
    workflow = StateGraph(TaskGraphState)

    # Add Nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("air_quality", air_quality_node)
    workflow.add_node("synthesis", synthesis_node)

    # Add Edges
    workflow.add_edge(START, "supervisor")

    # Conditional edge from supervisor to air_quality
    workflow.add_conditional_edges(
        "supervisor",
        route_by_complexity,
        {
            "air_quality": "air_quality",
        },
    )

    workflow.add_edge("air_quality", "synthesis")
    workflow.add_edge("synthesis", END)

    return workflow.compile(checkpointer=checkpointer)
