"""Wildfire Spread statistical model implementation."""

from __future__ import annotations

from orchestrator.schemas.agent_io import SimulationResult


class WildfireSpreadModel:
    """Coarse statistical approximation of wildfire propagation spread rate."""

    @property
    def model_name(self) -> str:
        return "WildfireSpreadModel"

    def run(self, parameters: dict) -> SimulationResult:
        wind_speed = parameters.get("wind_speed")
        temperature = parameters.get("temperature")

        if wind_speed is None:
            raise ValueError("Missing required input: wind_speed")
        if temperature is None:
            raise ValueError("Missing required input: temperature")

        # Sanity bound validation
        if not (0.0 <= wind_speed <= 80.0):
            raise ValueError("Parameter out of bounds: wind_speed")
        if not (10.0 <= temperature <= 55.0):
            raise ValueError("Parameter out of bounds: temperature")

        # Deterministic statistical calculation
        spread_rate = wind_speed * 0.4 + temperature * 0.1
        low_bound = spread_rate * 0.7
        high_bound = spread_rate * 1.3

        prediction = (
            f"Wildfire spread rate prediction: fire is propagating at "
            f"{spread_rate:.1f} meters per minute."
        )

        return SimulationResult(
            prediction=prediction,
            uncertainty_bounds=(low_bound, high_bound),
            assumptions=[
                "Homogeneous fuel distribution",
                "Zero slope baseline",
            ],
            model_used=self.model_name,
        )
