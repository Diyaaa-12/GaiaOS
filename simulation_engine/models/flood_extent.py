"""Flood Extent statistical model implementation."""

from __future__ import annotations

from orchestrator.schemas.agent_io import SimulationResult


class FloodExtentModel:
    """Coarse statistical approximation of flood extent."""

    @property
    def model_name(self) -> str:
        return "FloodExtentModel"

    def run(self, parameters: dict) -> SimulationResult:
        from simulation_engine.parameter_loader import load_calibrated_parameters

        rainfall = parameters.get("rainfall")
        if rainfall is None:
            raise ValueError("Missing required input: rainfall")

        # Sanity bound validation
        if not (5.0 <= rainfall <= 500.0):
            raise ValueError("Parameter out of bounds: rainfall")

        # Load calibrated parameters with defaults
        defaults = {
            "rainfall_coefficient": 3.2,
            "low_bound_factor": 2.8,
            "high_bound_factor": 3.6,
        }
        cal_params = load_calibrated_parameters("flood_extent", defaults)

        rain_coeff = cal_params.get("rainfall_coefficient", defaults["rainfall_coefficient"])
        low_factor = cal_params.get("low_bound_factor", defaults["low_bound_factor"])
        high_factor = cal_params.get("high_bound_factor", defaults["high_bound_factor"])

        # Deterministic statistical calculation
        flooded_area = rainfall * rain_coeff
        low_bound = rainfall * low_factor
        high_bound = rainfall * high_factor

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
