"""Protocol definition for Simulation Models."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from orchestrator.schemas.agent_io import SimulationResult


@runtime_checkable
class SimulationModel(Protocol):
    """Protocol that all simulation/prediction models must implement."""

    @property
    def model_name(self) -> str:
        """The identifier of the simulation model."""
        ...

    def run(self, parameters: dict) -> SimulationResult:
        """Run the statistical/coarse simulation and return the results.

        Raises:
            ValueError: If required parameters are missing or out of sanity bounds.
        """
        ...
