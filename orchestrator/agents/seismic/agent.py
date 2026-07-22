"""Seismic domain agent using USGS Seismic API client."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from orchestrator.schemas.agent_io import AgentInput, AgentOutput, Evidence
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


async def run(agent_input: AgentInput) -> AgentOutput:
    """Fetch earthquake listings near target region."""
    location = agent_input.region_hint or _extract_location(agent_input.query)
    evidence_list: list[Evidence] = []
    errors: list[str] = []

    try:
        geo = await geocode_location(location)
        client = USGSSeismicClient()
        features = await client.get_recent_earthquakes(
            lat=geo["lat"],
            lon=geo["lon"],
            radius_km=100.0,
            min_magnitude=1.0,
            days=7,
        )

        if not features:
            errors.append(f"No recent earthquakes found near {location}.")

        for feat in features:
            props = feat.get("properties", {})
            mag = props.get("mag")
            place = props.get("place")
            time_epoch = props.get("time", 0) / 1000.0
            dt = datetime.fromtimestamp(time_epoch, UTC)

            claim = f"Earthquake of magnitude {mag} occurred at '{place}' on {dt.isoformat()}."
            evidence_list.append(
                Evidence(
                    source="USGS Seismic API",
                    claim=claim,
                    confidence=0.98,
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
