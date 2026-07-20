"""Causal Chain agent for traversing historical hazard relationships using recursive CTEs."""

from __future__ import annotations

import re

from db.repository import find_causal_chain
from orchestrator.schemas.agent_io import AgentInput, AgentOutput


def _extract_location(query: str) -> str:
    match = re.search(
        r"\b(Tokyo|Japan|California|New York|Paris|London|Delhi|Madrid|Beijing)\b",
        query,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).capitalize()
    return "Tokyo"


def _extract_event_type(query: str) -> str:
    query_lower = query.lower()
    if "earthquake" in query_lower or "seismic" in query_lower:
        return "earthquake"
    if "wildfire" in query_lower or "fire" in query_lower:
        return "wildfire"
    if "heatwave" in query_lower or "marine heatwave" in query_lower:
        return "marine heatwave"
    return "earthquake"


async def run(agent_input: AgentInput) -> AgentOutput:
    """Run causal chain traversal over historical hazard events."""
    location = agent_input.region_hint or _extract_location(agent_input.query)
    event_type = _extract_event_type(agent_input.query)

    evidence_list = []
    errors = []

    try:
        evidence_list = await find_causal_chain(
            event_type=event_type,
            region=location,
            max_depth=4,
        )
    except TimeoutError as te:
        errors.append(f"causal chain query exceeded time budget: {str(te)}")
    except Exception as e:
        errors.append(f"Failed to query causal chain: {str(e)}")

    return AgentOutput(
        agent_name="causal_chain",
        evidence=evidence_list,
        errors=errors,
    )
