"""Air Quality domain agent.

Extracts PM2.5 and PM10 measurement readings from OpenAQ.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from config.settings import get_settings
from orchestrator.schemas.agent_io import AgentInput, AgentOutput, Evidence
from tools.air_quality_openaq.client import OpenAQClient


def _extract_city(query: str) -> str:
    """Fallback simple city parser for Milestone 2 query texts."""
    match = re.search(
        r"\b(Paris|Beijing|London|Delhi|Madrid|Tokyo)\b",
        query,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).capitalize()
    return "Paris"  # default fallback


async def run(agent_input: AgentInput) -> AgentOutput:
    """Query OpenAQ and format measurements as evidence items."""
    city = agent_input.region_hint or _extract_city(agent_input.query)

    settings = get_settings()
    api_key = settings.openaq_api_key

    client = OpenAQClient(api_key=api_key)
    evidence_list: list[Evidence] = []
    errors: list[str] = []

    try:
        results = await client.get_latest_measurements(city)
        if not results:
            errors.append(f"No active OpenAQ stations found for city: {city}")

        for res in results:
            location = res.get("location", "unknown")
            measurements = res.get("measurements", [])
            for meas in measurements:
                parameter = meas.get("parameter", "unknown")
                value = meas.get("value", 0.0)
                unit = meas.get("unit", "ug/m3")

                claim = (
                    f"At station '{location}' in {city}, the level of "
                    f"'{parameter}' is {value} {unit}."
                )

                evidence_list.append(
                    Evidence(
                        source=f"OpenAQ API (Station: {location})",
                        claim=claim,
                        confidence=0.95,  # direct sensor readings are highly confident
                        retrieved_at=datetime.now(UTC),
                    )
                )
    except Exception as e:
        errors.append(f"Failed to query OpenAQ for city {city}: {str(e)}")

    return AgentOutput(
        agent_name="air_quality",
        evidence=evidence_list,
        errors=errors,
    )
