"""Unit tests for the statistical simulation models."""

from __future__ import annotations

import pytest

from simulation_engine.models.enso_forecast import ENSOForecastModel
from simulation_engine.models.flood_extent import FloodExtentModel
from simulation_engine.models.plume_dispersion import PlumeDispersionModel
from simulation_engine.models.wildfire_spread import WildfireSpreadModel


class TestPlumeDispersionModel:
    """Verifies bounds checking and equations of PlumeDispersionModel."""

    def test_run_success(self) -> None:
        model = PlumeDispersionModel()
        res = model.run({"wind_speed": 10.0})
        assert res.model_used == "PlumeDispersionModel"
        assert "18.0 km" in res.prediction
        assert res.uncertainty_bounds == (15.0, 21.0)
        assert len(res.assumptions) == 2

    def test_missing_param(self) -> None:
        model = PlumeDispersionModel()
        with pytest.raises(ValueError, match="Missing required input"):
            model.run({})

    def test_out_of_bounds(self) -> None:
        model = PlumeDispersionModel()
        with pytest.raises(ValueError, match="Parameter out of bounds"):
            model.run({"wind_speed": 0.2})
        with pytest.raises(ValueError, match="Parameter out of bounds"):
            model.run({"wind_speed": 60.0})


class TestFloodExtentModel:
    """Verifies bounds checking and equations of FloodExtentModel."""

    def test_run_success(self) -> None:
        model = FloodExtentModel()
        res = model.run({"rainfall": 50.0})
        assert res.model_used == "FloodExtentModel"
        assert "160.0 square" in res.prediction
        assert res.uncertainty_bounds == (140.0, 180.0)

    def test_missing_param(self) -> None:
        model = FloodExtentModel()
        with pytest.raises(ValueError, match="Missing required input"):
            model.run({})

    def test_out_of_bounds(self) -> None:
        model = FloodExtentModel()
        with pytest.raises(ValueError, match="Parameter out of bounds"):
            model.run({"rainfall": 2.0})
        with pytest.raises(ValueError, match="Parameter out of bounds"):
            model.run({"rainfall": 600.0})


class TestWildfireSpreadModel:
    """Verifies bounds checking and equations of WildfireSpreadModel."""

    def test_run_success(self) -> None:
        model = WildfireSpreadModel()
        res = model.run({"wind_speed": 20.0, "temperature": 30.0})
        assert res.model_used == "WildfireSpreadModel"
        # spread_rate = 20.0 * 0.4 + 30.0 * 0.1 = 11.0
        assert "11.0 meters" in res.prediction
        assert res.uncertainty_bounds == pytest.approx((7.7, 14.3))

    def test_missing_param(self) -> None:
        model = WildfireSpreadModel()
        with pytest.raises(ValueError, match="Missing required input"):
            model.run({"wind_speed": 10.0})
        with pytest.raises(ValueError, match="Missing required input"):
            model.run({"temperature": 25.0})

    def test_out_of_bounds(self) -> None:
        model = WildfireSpreadModel()
        with pytest.raises(ValueError, match="Parameter out of bounds"):
            model.run({"wind_speed": -5.0, "temperature": 30.0})
        with pytest.raises(ValueError, match="Parameter out of bounds"):
            model.run({"wind_speed": 20.0, "temperature": 60.0})


class TestENSOForecastModel:
    """Verifies bounds checking and equations of ENSOForecastModel."""

    def test_run_success_el_nino(self) -> None:
        model = ENSOForecastModel()
        res = model.run({"sst_anomaly": 1.2})
        assert "El Niño" in res.prediction
        assert res.uncertainty_bounds == pytest.approx((1.0, 1.4))

    def test_run_success_la_nina(self) -> None:
        model = ENSOForecastModel()
        res = model.run({"sst_anomaly": -0.8})
        assert "La Niña" in res.prediction

    def test_run_success_neutral(self) -> None:
        model = ENSOForecastModel()
        res = model.run({"sst_anomaly": 0.1})
        assert "Neutral" in res.prediction

    def test_out_of_bounds(self) -> None:
        model = ENSOForecastModel()
        with pytest.raises(ValueError, match="Parameter out of bounds"):
            model.run({"sst_anomaly": 5.0})
