"""Plume Dispersion statistical model implementation."""

from __future__ import annotations

from orchestrator.schemas.agent_io import SimulationResult


class PlumeDispersionModel:
    """Statistical approximation of a gas plume dispersion."""

    @property
    def model_name(self) -> str:
        return "PlumeDispersionModel"

    def run(self, parameters: dict) -> SimulationResult:
        wind_speed = parameters.get("wind_speed")
        if wind_speed is None:
            raise ValueError("Missing required input: wind_speed")

        # Sanity bound validation
        if not (0.5 <= wind_speed <= 50.0):
            raise ValueError("Parameter out of bounds: wind_speed")

        # Deterministic statistical calculation
        dispersion_distance = wind_speed * 1.8
        low_bound = wind_speed * 1.5
        high_bound = wind_speed * 2.1

        prediction = (
            f"Plume dispersion prediction: plume will disperse up to "
            f"{dispersion_distance:.1f} km downwind."
        )

        return SimulationResult(
            prediction=prediction,
            uncertainty_bounds=(low_bound, high_bound),
            assumptions=[
                "Wind speed remains constant",
                "Point source emission at 10m height",
            ],
            model_used=self.model_name,
        )
