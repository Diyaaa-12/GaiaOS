"""Atmosphere domain agent using Open-Meteo weather client."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from orchestrator.schemas.agent_io import AgentInput, AgentOutput, Evidence
from tools.geocoding import geocode_location
from tools.weather.client import WeatherClient


def _extract_location(query: str) -> str:
    match = re.search(
        r"\b(Tokyo|Japan|California|New York|Paris|London|Delhi|Madrid|Beijing)\b",
        query,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).capitalize()
    return "Tokyo"


async def run(agent_input: AgentInput) -> AgentOutput:
    """Fetch current weather metrics from Open-Meteo."""
    location = agent_input.region_hint or _extract_location(agent_input.query)
    evidence_list: list[Evidence] = []
    errors: list[str] = []

    try:
        geo = await geocode_location(location)
        client = WeatherClient()
        data = await client.get_current_weather(geo["lat"], geo["lon"])

        current = data.get("current", {})
        if not current:
            errors.append(f"No atmospheric data returned for {location}.")
        else:
            temp = current.get("temperature_2m")
            wind = current.get("wind_speed_10m")
            humidity = current.get("relative_humidity_2m")
            claim = (
                f"Current atmospheric conditions in {location}: "
                f"Temperature is {temp}°C, Wind Speed is {wind} km/h, "
                f"and Relative Humidity is {humidity}%."
            )
            evidence_list.append(
                Evidence(
                    source="Open-Meteo Weather API",
                    claim=claim,
                    confidence=0.95,
                    retrieved_at=datetime.now(UTC),
                )
            )
    except Exception as e:
        errors.append(f"Failed to query Open-Meteo weather for {location}: {str(e)}")

    return AgentOutput(
        agent_name="atmosphere",
        evidence=evidence_list,
        errors=errors,
    )
