"""ENSO Forecast statistical model implementation."""

from __future__ import annotations

from orchestrator.schemas.agent_io import SimulationResult


class ENSOForecastModel:
    """Coarse statistical approximation of El Nino/Southern Oscillation conditions."""

    @property
    def model_name(self) -> str:
        return "ENSOForecastModel"

    def run(self, parameters: dict) -> SimulationResult:
        sst_anomaly = parameters.get("sst_anomaly")
        if sst_anomaly is None:
            raise ValueError("Missing required input: sst_anomaly")

        # Sanity bound validation
        if not (-4.0 <= sst_anomaly <= 4.0):
            raise ValueError("Parameter out of bounds: sst_anomaly")

        # Deterministic statistical calculation
        if sst_anomaly >= 0.5:
            state = "El Niño"
        elif sst_anomaly <= -0.5:
            state = "La Niña"
        else:
            state = "Neutral"

        prediction = f"ENSO Forecast prediction: current SST anomaly indicates {state} conditions."
        low_bound = sst_anomaly - 0.2
        high_bound = sst_anomaly + 0.2

        return SimulationResult(
            prediction=prediction,
            uncertainty_bounds=(low_bound, high_bound),
            assumptions=[
                "Sea surface temperature anomalies persist for at least 3 months",
                "Niño 3.4 region monitoring baseline",
            ],
            model_used=self.model_name,
        )
