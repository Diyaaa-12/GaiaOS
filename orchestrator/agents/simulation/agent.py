"""Simulation Agent orchestration implementation."""

from __future__ import annotations

import re

from logging_config import get_logger
from orchestrator.schemas.agent_io import AgentInput, AgentOutput, Evidence
from simulation_engine import run_simulation

_log = get_logger(__name__)


def _extract_hazard_type(query: str) -> str | None:
    """Extract hazard type from the query string."""
    q = query.lower()
    if "plume" in q or "dispersion" in q:
        return "plume"
    if "flood" in q:
        return "flood"
    if "wildfire" in q or "fire" in q:
        return "wildfire"
    if "enso" in q or "nino" in q or "nina" in q:
        return "enso"
    return None


def _extract_parameters(query: str, prior_outputs: list[AgentOutput] | None) -> dict[str, float]:
    """Extract required parameters from prior evidence claims or query text."""
    params: dict[str, float] = {}

    # 1. Parse from prior evidence claims
    if prior_outputs:
        for out in prior_outputs:
            for ev in out.evidence:
                claim = ev.claim

                # Match wind speed (e.g. "Wind Speed is 15.4 km/h" or "15.4 m/s")
                ws_match = re.search(r"Wind Speed is\s*([\d.]+)", claim, re.IGNORECASE)
                if ws_match and "wind_speed" not in params:
                    params["wind_speed"] = float(ws_match.group(1))

                # Match temperature (e.g. "Temperature is 22.1°C")
                temp_match = re.search(r"Temperature is\s*([\d.]+)", claim, re.IGNORECASE)
                if temp_match and "temperature" not in params:
                    params["temperature"] = float(temp_match.group(1))

                # Match precipitation / rainfall (e.g. "Precipitation is 15.2 mm")
                rain_match = re.search(
                    r"(?:rainfall|precipitation|precip)\s*(?:is|of)?\s*([\d.]+)",
                    claim,
                    re.IGNORECASE,
                )
                if rain_match and "rainfall" not in params:
                    params["rainfall"] = float(rain_match.group(1))

                # Match SST anomaly (e.g. "SST anomaly is 1.2°C")
                sst_match = re.search(
                    r"sst[-_ ]anomaly\s*(?:is|of)?\s*([\d.]+)", claim, re.IGNORECASE
                )
                if sst_match and "sst_anomaly" not in params:
                    params["sst_anomaly"] = float(sst_match.group(1))

    # 2. Fallback: Parse from query text if still missing
    q_lower = query.lower()
    if "wind_speed" not in params:
        ws_q = re.search(r"wind[-_ ]speed\s*(?:is|of)?\s*([\d.]+)", q_lower)
        if ws_q:
            params["wind_speed"] = float(ws_q.group(1))

    if "temperature" not in params:
        temp_q = re.search(r"temp(?:erature)?\s*(?:is|of)?\s*([\d.]+)", q_lower)
        if temp_q:
            params["temperature"] = float(temp_q.group(1))

    if "rainfall" not in params:
        rain_q = re.search(r"(?:rainfall|precipitation)\s*(?:is|of)?\s*([\d.]+)", q_lower)
        if rain_q:
            params["rainfall"] = float(rain_q.group(1))

    if "sst_anomaly" not in params:
        sst_q = re.search(r"sst[-_ ]anomaly\s*(?:is|of)?\s*([\d.]+)", q_lower)
        if sst_q:
            params["sst_anomaly"] = float(sst_q.group(1))

    return params


async def run(
    agent_input: AgentInput, prior_outputs: list[AgentOutput] | None = None
) -> AgentOutput:
    """Execute the simulation model matching the query's hazard type."""
    query = agent_input.query
    hazard_type = _extract_hazard_type(query)

    if not hazard_type:
        _log.error("simulation.agent.unknown_hazard", query=query)
        return AgentOutput(
            agent_name="simulation",
            errors=["Unknown or unsupported hazard simulation query."],
        )

    parameters = _extract_parameters(query, prior_outputs)
    region = agent_input.region_hint or "global"

    _log.info(
        "simulation.agent.starting",
        hazard_type=hazard_type,
        region=region,
        parameters=parameters,
    )

    try:
        # Run simulation model through registry wrapper
        result = await run_simulation(hazard_type, region, parameters)

        _log.info(
            "simulation.agent.success",
            model_used=result.model_used,
            parameters=parameters,
            sanity_check_result="passed",
        )

        evidence = Evidence(
            source=result.model_used,
            claim=result.prediction,
            confidence=0.90,  # baseline simulation confidence
            uncertainty_bounds=result.uncertainty_bounds,
            assumptions=result.assumptions,
            extra_metadata={"model_used": result.model_used},
        )

        return AgentOutput(
            agent_name="simulation",
            evidence=[evidence],
        )

    except ValueError as e:
        msg = str(e)
        if "Missing required input" in msg:
            _log.error(
                "simulation.agent.missing_parameter",
                hazard_type=hazard_type,
                parameters=parameters,
                error=msg,
            )
            return AgentOutput(agent_name="simulation", errors=[msg])
        else:
            # Sanity bound violation check failure path
            _log.error(
                "simulation.agent.sanity_check_failed",
                hazard_type=hazard_type,
                parameters=parameters,
                error=msg,
                sanity_check_result="failed",
            )
            return AgentOutput(
                agent_name="simulation",
                errors=["simulation inconclusive"],
            )
    except Exception as e:
        _log.error(
            "simulation.agent.unexpected_failure",
            hazard_type=hazard_type,
            error=str(e),
        )
        return AgentOutput(
            agent_name="simulation",
            errors=["simulation inconclusive"],
        )
