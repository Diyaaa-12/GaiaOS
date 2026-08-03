"""Causal Chain agent for traversing historical hazard relationships using recursive CTEs."""

from __future__ import annotations

import re

from config.settings import get_settings
from db.repository import find_causal_chain
from orchestrator.graph.collaboration_bus import CollaborationBus
from orchestrator.schemas.agent_io import AgentInput, AgentOutput
from tools.geocoding import geocode_location


def _extract_location(query: str) -> str:
    match = re.search(
        r"\b(Tokyo|Japan|California|New York|Paris|London|Delhi|Madrid|Beijing)\b",
        query,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).capitalize()
    return query


def _extract_event_type(query: str) -> str:
    query_lower = query.lower()
    if "satellite wildfire" in query_lower or "copernicus" in query_lower:
        return "wildfire_satellite"
    if "atmospheric anomaly" in query_lower or "era5" in query_lower or "reanalysis" in query_lower:
        return "atmospheric_anomaly"
    if (
        "unrest" in query_lower
        or "gdelt" in query_lower
        or "civil" in query_lower
        or "socio" in query_lower
    ):
        return "civil_unrest_hazard_adjacent"
    if "earthquake" in query_lower or "seismic" in query_lower:
        return "earthquake"
    if "wildfire" in query_lower or "fire" in query_lower:
        return "wildfire"
    if "heatwave" in query_lower or "marine heatwave" in query_lower:
        return "marine heatwave"
    return "earthquake"



async def run(agent_input: AgentInput, bus: CollaborationBus | None = None) -> AgentOutput:
    """Run causal chain traversal over historical hazard events."""
    location = agent_input.region_hint or _extract_location(agent_input.query)
    event_type = _extract_event_type(agent_input.query)

    evidence_list = []
    errors = []

    # 1. Resolve location to latitude/longitude via existing geocoding tool
    try:
        geo = await geocode_location(location)
        point = (geo["lat"], geo["lon"])
    except ValueError:
        return AgentOutput(
            agent_name="causal_chain",
            evidence=[],
            errors=["could not resolve region for causal analysis"],
        )
    except Exception as ge:
        return AgentOutput(
            agent_name="causal_chain",
            evidence=[],
            errors=[f"could not resolve region for causal analysis: {str(ge)}"],
        )

    # 2. Query causal chain repository using PostGIS spatial proximity
    settings = get_settings()
    radius_meters = settings.causal_chain_search_radius_meters

    try:
        evidence_list = await find_causal_chain(
            event_type=event_type,
            point=point,
            radius_meters=radius_meters,
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
