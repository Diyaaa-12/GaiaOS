"""ENSO Forecast statistical model implementation."""

from __future__ import annotations

from orchestrator.schemas.agent_io import SimulationResult


class ENSOForecastModel:
    """Coarse statistical approximation of El Nino/Southern Oscillation conditions."""

    @property
    def model_name(self) -> str:
        return "ENSOForecastModel"

    def run(self, parameters: dict) -> SimulationResult:
        from simulation_engine.parameter_loader import load_calibrated_parameters

        sst_anomaly = parameters.get("sst_anomaly")
        if sst_anomaly is None:
            raise ValueError("Missing required input: sst_anomaly")

        # Sanity bound validation
        if not (-4.0 <= sst_anomaly <= 4.0):
            raise ValueError("Parameter out of bounds: sst_anomaly")

        # Load calibrated parameters with defaults
        defaults = {
            "el_nino_threshold": 0.5,
            "la_nina_threshold": -0.5,
            "low_bound_offset": -0.2,
            "high_bound_offset": 0.2,
        }
        cal_params = load_calibrated_parameters("enso_forecast", defaults)

        nino_thresh = cal_params.get("el_nino_threshold", defaults["el_nino_threshold"])
        nina_thresh = cal_params.get("la_nina_threshold", defaults["la_nina_threshold"])
        low_offset = cal_params.get("low_bound_offset", defaults["low_bound_offset"])
        high_offset = cal_params.get("high_bound_offset", defaults["high_bound_offset"])

        # Deterministic statistical calculation
        if sst_anomaly >= nino_thresh:
            state = "El Niño"
        elif sst_anomaly <= nina_thresh:
            state = "La Niña"
        else:
            state = "Neutral"

        prediction = f"ENSO Forecast prediction: current SST anomaly indicates {state} conditions."
        low_bound = sst_anomaly + low_offset
        high_bound = sst_anomaly + high_offset

        return SimulationResult(
            prediction=prediction,
            uncertainty_bounds=(low_bound, high_bound),
            assumptions=[
                "Sea surface temperature anomalies persist for at least 3 months",
                "Niño 3.4 region monitoring baseline",
            ],
            model_used=self.model_name,
        )
