"""Ocean domain agent using NOAA Ocean API client."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from orchestrator.schemas.agent_io import AgentInput, AgentOutput, Evidence
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


async def run(agent_input: AgentInput) -> AgentOutput:
    """Fetch sea surface temperature measurements from NOAA."""
    location = agent_input.region_hint or _extract_location(agent_input.query)
    evidence_list: list[Evidence] = []
    errors: list[str] = []

    try:
        geo = await geocode_location(location)
        station_id = geo.get("station_id", "8518750")
        client = NOAAOceanClient()
        data = await client.get_water_temperature(station_id)

        if not data or "data" not in data:
            errors.append(
                f"No active NOAA ocean measurements found for station {station_id} ({location})."
            )
        else:
            measurements = data.get("data", [])
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
                        confidence=0.95,
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
