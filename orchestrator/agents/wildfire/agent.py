"""Wildfire domain agent using NASA FIRMS active fire client."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from config.settings import get_settings
from orchestrator.schemas.agent_io import AgentInput, AgentOutput, Evidence
from tools.geocoding import geocode_location
from tools.wildfire_firms.client import FIRMSWildfireClient


def _extract_location(query: str) -> str:
    match = re.search(
        r"\b(Tokyo|Japan|California|New York|Paris|London|Delhi|Madrid|Beijing)\b",
        query,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).capitalize()
    return "California"


async def run(agent_input: AgentInput) -> AgentOutput:
    """Fetch active fire counts from NASA FIRMS API."""
    location = agent_input.region_hint or _extract_location(agent_input.query)
    evidence_list: list[Evidence] = []
    errors: list[str] = []

    try:
        geo = await geocode_location(location)
        bbox = geo["bbox"]

        settings = get_settings()
        api_key = settings.firms_api_key

        client = FIRMSWildfireClient(api_key=api_key)
        fires = await client.get_active_fires(
            min_x=bbox[0],
            min_y=bbox[1],
            max_x=bbox[2],
            max_y=bbox[3],
            days=1,
        )

        if not fires:
            if not api_key:
                errors.append(
                    "NASA FIRMS API key is not configured; skipped wildfire active search."
                )
            else:
                errors.append(f"No active wildfires reported in {location} region.")
        else:
            for fire in fires[:10]:
                lat = fire.get("latitude")
                lon = fire.get("longitude")
                conf = fire.get("confidence", "nominal")
                acq_date = fire.get("acq_date")
                acq_time = fire.get("acq_time")

                claim = (
                    f"Active fire detected in {location} region at coordinates ({lat}, {lon}) "
                    f"with confidence '{conf}' on {acq_date} {acq_time}."
                )
                confidence_score = 0.90 if conf in ("h", "100") else 0.70
                evidence_list.append(
                    Evidence(
                        source="NASA FIRMS API",
                        claim=claim,
                        confidence=confidence_score,
                        retrieved_at=datetime.now(UTC),
                    )
                )
    except Exception as e:
        errors.append(f"Failed to query FIRMS wildfire API for {location}: {str(e)}")

    return AgentOutput(
        agent_name="wildfire",
        evidence=evidence_list,
        errors=errors,
    )
