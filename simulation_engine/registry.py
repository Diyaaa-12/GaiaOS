"""Registry to manage and retrieve simulation models."""

from __future__ import annotations

from simulation_engine.models.base import SimulationModel
from simulation_engine.models.enso_forecast import ENSOForecastModel
from simulation_engine.models.flood_extent import FloodExtentModel
from simulation_engine.models.plume_dispersion import PlumeDispersionModel
from simulation_engine.models.wildfire_spread import WildfireSpreadModel


class ModelRegistry:
    """Registry managing registered simulation models by hazard name."""

    _models: dict[str, SimulationModel] = {}

    @classmethod
    def register(cls, hazard_type: str, model: SimulationModel) -> None:
        """Register a simulation model for a specific hazard type."""
        cls._models[hazard_type.lower()] = model

    @classmethod
    def get(cls, hazard_type: str) -> SimulationModel | None:
        """Retrieve a simulation model registered for a specific hazard type."""
        return cls._models.get(hazard_type.lower())


# Auto-register default models
ModelRegistry.register("plume", PlumeDispersionModel())
ModelRegistry.register("plume_dispersion", PlumeDispersionModel())
ModelRegistry.register("flood", FloodExtentModel())
ModelRegistry.register("flood_extent", FloodExtentModel())
ModelRegistry.register("wildfire", WildfireSpreadModel())
ModelRegistry.register("wildfire_spread", WildfireSpreadModel())
ModelRegistry.register("enso", ENSOForecastModel())
ModelRegistry.register("enso_forecast", ENSOForecastModel())
