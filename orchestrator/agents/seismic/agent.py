"""Seismic domain agent using USGS Seismic API client."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from orchestrator.graph.collaboration_bus import CollaborationBus
from orchestrator.schemas.agent_io import AgentInput, AgentOutput, Evidence
from orchestrator.schemas.uncertainty import UncertaintyEstimate
from tools.geocoding import geocode_location
from tools.seismic_usgs.client import USGSSeismicClient


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
    """Fetch earthquake listings near target region."""
    location = agent_input.region_hint or _extract_location(agent_input.query)
    evidence_list: list[Evidence] = []
    errors: list[str] = []

    try:
        geo = await geocode_location(location)
        client = USGSSeismicClient()
        result = await client.get_recent_earthquakes(
            lat=geo["lat"],
            lon=geo["lon"],
            radius_km=100.0,
            min_magnitude=1.0,
            days=7,
        )

        # Propagate degraded flag into errors (informational, non-fatal)
        if result.degraded:
            errors.append(f"[degraded:usgs] {result.source_status} — serving stale seismic data")

        features = result.value or []

        if not features:
            errors.append(f"No recent earthquakes found near {location}.")
        elif bus is not None:
            from orchestrator.schemas.collaboration import CollaborationMessage

            top_feat = features[0]
            props = top_feat.get("properties", {})
            mag = props.get("mag", 0.0)
            place = props.get("place", location)
            await bus.broadcast(
                CollaborationMessage(
                    from_agent="seismic",
                    finding_summary=f"Recent earthquake magnitude {mag} near {place}.",
                    uncertainty=UncertaintyEstimate.from_point_estimate(
                        0.95, source="well_supported"
                    ),
                    suggested_refinement={"region_hint": location},
                    round=0,
                )
            )

        for feat in features:
            props = feat.get("properties", {})
            mag = props.get("mag")
            place = props.get("place")
            time_epoch = props.get("time", 0) / 1000.0
            dt = datetime.fromtimestamp(time_epoch, UTC)

            # Use data_sparsity when serving cached/stale data
            uncertainty_source = "data_sparsity" if result.degraded else "well_supported"
            claim = f"Earthquake of magnitude {mag} occurred at '{place}' on {dt.isoformat()}."
            evidence_list.append(
                Evidence(
                    source="USGS Seismic API",
                    claim=claim,
                    uncertainty=UncertaintyEstimate.from_point_estimate(
                        0.98 if not result.degraded else 0.7,
                        source=uncertainty_source,
                    ),
                    retrieved_at=datetime.now(UTC),
                )
            )
    except Exception as e:
        errors.append(f"Failed to query USGS for {location}: {str(e)}")

    return AgentOutput(
        agent_name="seismic",
        evidence=evidence_list,
        errors=errors,
    )
