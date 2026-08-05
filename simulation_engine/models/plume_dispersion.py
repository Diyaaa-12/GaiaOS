"""Plume Dispersion statistical model implementation."""

from __future__ import annotations

from orchestrator.schemas.agent_io import SimulationResult


class PlumeDispersionModel:
    """Statistical approximation of a gas plume dispersion."""

    @property
    def model_name(self) -> str:
        return "PlumeDispersionModel"

    def run(self, parameters: dict) -> SimulationResult:
        from simulation_engine.parameter_loader import load_calibrated_parameters

        wind_speed = parameters.get("wind_speed")
        if wind_speed is None:
            raise ValueError("Missing required input: wind_speed")

        # Sanity bound validation
        if not (0.5 <= wind_speed <= 50.0):
            raise ValueError("Parameter out of bounds: wind_speed")

        # Load calibrated parameters with defaults
        defaults = {
            "wind_coefficient": 1.8,
            "low_bound_factor": 1.5,
            "high_bound_factor": 2.1,
        }
        cal_params = load_calibrated_parameters("plume_dispersion", defaults)

        wind_coeff = cal_params.get("wind_coefficient", defaults["wind_coefficient"])
        low_factor = cal_params.get("low_bound_factor", defaults["low_bound_factor"])
        high_factor = cal_params.get("high_bound_factor", defaults["high_bound_factor"])

        # Deterministic statistical calculation
        dispersion_distance = wind_speed * wind_coeff
        low_bound = wind_speed * low_factor
        high_bound = wind_speed * high_factor

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
