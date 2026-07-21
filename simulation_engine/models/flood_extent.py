"""Flood Extent statistical model implementation."""

from __future__ import annotations

from orchestrator.schemas.agent_io import SimulationResult


class FloodExtentModel:
    """Coarse statistical approximation of flood extent."""

    @property
    def model_name(self) -> str:
        return "FloodExtentModel"

    def run(self, parameters: dict) -> SimulationResult:
        rainfall = parameters.get("rainfall")
        if rainfall is None:
            raise ValueError("Missing required input: rainfall")

        # Sanity bound validation
        if not (5.0 <= rainfall <= 500.0):
            raise ValueError("Parameter out of bounds: rainfall")

        # Deterministic statistical calculation
        flooded_area = rainfall * 3.2
        low_bound = rainfall * 2.8
        high_bound = rainfall * 3.6

        prediction = (
            f"Flood extent prediction: total flooded area is estimated at "
            f"{flooded_area:.1f} square kilometers."
        )

        return SimulationResult(
            prediction=prediction,
            uncertainty_bounds=(low_bound, high_bound),
            assumptions=[
                "Soil is fully saturated",
                "Flat topography baseline approximation",
            ],
            model_used=self.model_name,
        )
