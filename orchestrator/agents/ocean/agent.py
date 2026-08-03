"""Ocean domain agent using NOAA Ocean API client."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from orchestrator.graph.collaboration_bus import CollaborationBus
from orchestrator.schemas.agent_io import AgentInput, AgentOutput, Evidence
from orchestrator.schemas.collaboration import CollaborationMessage
from orchestrator.schemas.uncertainty import UncertaintyEstimate
from tools.geocoding import geocode_location
from tools.ocean_noaa.client import NOAAOceanClient


def _extract_location(query: str) -> str:
    match = re.search(
        r"\b(Tokyo|Japan|California|New York|Paris|London|Delhi|Madrid|Beijing)\b",
        query,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).capitalize()
    return query


async def run(agent_input: AgentInput, bus: CollaborationBus | None = None) -> AgentOutput:
    """Fetch sea surface temperature measurements from NOAA."""
    location = agent_input.region_hint or _extract_location(agent_input.query)
    evidence_list: list[Evidence] = []
    errors: list[str] = []

    try:
        geo = await geocode_location(location)
        station_id = geo.get("station_id")
        if not station_id:
            errors.append(f"No active NOAA ocean station found for location '{location}'.")
            return AgentOutput(agent_name="ocean", evidence=[], errors=errors)

        client = NOAAOceanClient()
        result = await client.get_water_temperature(station_id)

        # Propagate degraded flag into errors (informational, non-fatal)
        if result.degraded:
            errors.append(f"[degraded:noaa] {result.source_status} — serving stale ocean data")

        data = result.value or {}

        if not data or "data" not in data:
            errors.append(
                f"No active NOAA ocean measurements found for station {station_id} ({location})."
            )
        else:
            measurements = data.get("data", [])
            uncertainty_source = "data_sparsity" if result.degraded else "well_supported"
            for meas in measurements[:5]:
                time_str = meas.get("t")
                temp = meas.get("v")
                claim = (
                    f"At NOAA ocean station {station_id} ({location}), "
                    f"water temperature was recorded as {temp} °C at {time_str}."
                )
                evidence_list.append(
                    Evidence(
                        source=f"NOAA Ocean API (Station: {station_id})",
                        claim=claim,
                        uncertainty=UncertaintyEstimate.from_point_estimate(
                            0.95 if not result.degraded else 0.6,
                            source=uncertainty_source,
                        ),
                        retrieved_at=datetime.now(UTC),
                    )
                )
    except Exception as e:
        errors.append(f"Failed to query NOAA for {location}: {str(e)}")

    return AgentOutput(
        agent_name="ocean",
        evidence=evidence_list,
        errors=errors,
    )


def on_peer_finding(message: CollaborationMessage, agent_input: AgentInput) -> AgentInput | None:
    """Refining hook for ocean agent when receiving peer findings.

    If peer seismic agent broadcasts a seismic finding with a region hint,
    and ocean agent's current region_hint does not match, return a refined input.
    """
    if message.from_agent == "seismic" and message.suggested_refinement:
        region = message.suggested_refinement.get("region_hint")
        if region and agent_input.region_hint != region:
            return AgentInput(
                investigation_id=agent_input.investigation_id,
                query=agent_input.query,
                region_hint=region,
            )
    return None


# Attach collaboration peer finding hook to runner callable
run.on_peer_finding = on_peer_finding  # type: ignore[attr-defined]
