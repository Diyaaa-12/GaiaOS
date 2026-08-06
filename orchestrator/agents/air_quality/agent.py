"""Air Quality domain agent.

Extracts PM2.5 and PM10 measurement readings from OpenAQ.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from config.settings import get_settings
from metrics.collector import (
    LOCATION_REGEX_FALLBACK_TOTAL,
    PLANNER_REGION_HINT_MISSING_TOTAL,
)
from orchestrator.graph.collaboration_bus import CollaborationBus
from orchestrator.schemas.agent_io import AgentInput, AgentOutput, Evidence
from orchestrator.schemas.uncertainty import SourceType, UncertaintyEstimate
from tools.air_quality_openaq.client import OpenAQClient


def _extract_city(query: str) -> str:
    """Fallback simple city parser for Milestone 2 query texts."""
    LOCATION_REGEX_FALLBACK_TOTAL.labels(agent="air_quality").inc()
    match = re.search(
        r"\b(Paris|London|Delhi|Madrid|Beijing|Tokyo|New York)\b",
        query,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).capitalize()
    return "Paris"  # default fallback


async def run(agent_input: AgentInput, bus: CollaborationBus | None = None) -> AgentOutput:
    """Query OpenAQ and format measurements as evidence items."""
    if not agent_input.region_hint:
        PLANNER_REGION_HINT_MISSING_TOTAL.labels(agent="air_quality").inc()
        city = _extract_city(agent_input.query)
    else:
        city = agent_input.region_hint

    settings = get_settings()
    api_key = settings.openaq_api_key

    client = OpenAQClient(api_key=api_key)
    evidence_list: list[Evidence] = []
    errors: list[str] = []

    try:
        result = await client.get_latest_measurements(city)

        # Propagate degraded flag into errors (informational, non-fatal)
        if result.degraded:
            errors.append(
                f"[degraded:openaq] {result.source_status} — serving stale air quality data"
            )

        results = result.value or []
        if not results:
            errors.append(f"No active OpenAQ stations found for city: {city}")

        uncertainty_source: SourceType = (
            "data_sparsity" if result.degraded else "well_supported"
        )
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
                        uncertainty=UncertaintyEstimate.from_point_estimate(
                            0.95 if not result.degraded else 0.6,
                            source=uncertainty_source,
                        ),
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
