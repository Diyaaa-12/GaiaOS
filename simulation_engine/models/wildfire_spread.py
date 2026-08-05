"""Wildfire Spread statistical model implementation."""

from __future__ import annotations

from orchestrator.schemas.agent_io import SimulationResult


class WildfireSpreadModel:
    """Coarse statistical approximation of wildfire propagation spread rate."""

    @property
    def model_name(self) -> str:
        return "WildfireSpreadModel"

    def run(self, parameters: dict) -> SimulationResult:
        from simulation_engine.parameter_loader import load_calibrated_parameters

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

        # Load calibrated parameters with defaults
        defaults = {
            "wind_coefficient": 0.4,
            "temp_coefficient": 0.1,
            "low_bound_factor": 0.7,
            "high_bound_factor": 1.3,
        }
        cal_params = load_calibrated_parameters("wildfire_spread", defaults)

        wind_coeff = cal_params.get("wind_coefficient", defaults["wind_coefficient"])
        temp_coeff = cal_params.get("temp_coefficient", defaults["temp_coefficient"])
        low_factor = cal_params.get("low_bound_factor", defaults["low_bound_factor"])
        high_factor = cal_params.get("high_bound_factor", defaults["high_bound_factor"])

        # Deterministic statistical calculation using calibrated coefficients
        spread_rate = wind_speed * wind_coeff + temperature * temp_coeff
        low_bound = spread_rate * low_factor
        high_bound = spread_rate * high_factor

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
