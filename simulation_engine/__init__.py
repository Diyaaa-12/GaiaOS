"""Simulation engine package exports and public interface."""

from __future__ import annotations

from orchestrator.schemas.agent_io import SimulationResult
from simulation_engine.registry import ModelRegistry


async def run_simulation(hazard_type: str, region: str, parameters: dict) -> SimulationResult:
    """Run a registered simulation model for the given hazard type and parameters.

    Raises:
        ValueError: If no model is found for hazard_type, or if sanity check fails.
    """
    model = ModelRegistry.get(hazard_type)
    if not model:
        raise ValueError(f"No simulation model registered for hazard: {hazard_type}")

    # run() is a CPU-bound/local deterministic method.
    return model.run(parameters)
