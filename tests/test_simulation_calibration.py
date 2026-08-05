"""Unit and integration tests for simulation model parameter calibration."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml  # type: ignore
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from simulation_engine.calibration.fit_enso_forecast import fit_enso_forecast
from simulation_engine.calibration.fit_flood_extent import fit_flood_extent
from simulation_engine.calibration.fit_plume_dispersion import fit_plume_dispersion
from simulation_engine.calibration.fit_wildfire_spread import fit_wildfire_spread
from simulation_engine.calibration.outcome_extractor import (
    extract_observed_outcome,
)
from simulation_engine.calibration.report import check_and_promote_parameters
from simulation_engine.models.enso_forecast import ENSOForecastModel
from simulation_engine.models.flood_extent import FloodExtentModel
from simulation_engine.models.plume_dispersion import PlumeDispersionModel
from simulation_engine.models.wildfire_spread import WildfireSpreadModel
from simulation_engine.parameter_loader import (
    invalidate_parameter_cache,
    load_calibrated_parameters,
)
from workers.jobs.calibration_job import _async_run_calibration_job


# Define a minimal class conforming to the ObservableEvent Protocol
class DummyEvent:
    def __init__(self, details: str | None) -> None:
        self.details = details


@pytest.mark.asyncio
async def test_simulation_fallback_when_config_missing() -> None:
    """Verify that models run correctly using default constants when config is missing."""
    invalidate_parameter_cache()
    # Ensure no config files are loaded
    with patch("simulation_engine.parameter_loader.Path.is_file", return_value=False):
        wf = WildfireSpreadModel()
        wf_res = wf.run({"wind_speed": 10.0, "temperature": 25.0})
        # Default: 10 * 0.4 + 25 * 0.1 = 6.5
        assert "6.5 meters" in wf_res.prediction

        fld = FloodExtentModel()
        fld_res = fld.run({"rainfall": 10.0})
        # Default: 10 * 3.2 = 32.0
        assert "32.0 square" in fld_res.prediction

        plm = PlumeDispersionModel()
        plm_res = plm.run({"wind_speed": 10.0})
        # Default: 10 * 1.8 = 18.0
        assert "18.0 km" in plm_res.prediction

        enso = ENSOForecastModel()
        enso_res = enso.run({"sst_anomaly": 0.8})
        assert "El Niño" in enso_res.prediction


def test_wildfire_spread_fitter_math() -> None:
    """Verify wildfire spread closed-form regression math."""
    train_samples = [
        {"wind_speed": 5.0, "temperature": 15.0, "observed": 3.8},
        {"wind_speed": 10.0, "temperature": 20.0, "observed": 6.4},
        {"wind_speed": 15.0, "temperature": 25.0, "observed": 9.0},
        {"wind_speed": 20.0, "temperature": 30.0, "observed": 11.6},
        {"wind_speed": 25.0, "temperature": 35.0, "observed": 14.2},
    ]
    val_samples = [
        {"wind_speed": 12.0, "temperature": 22.0, "observed": 7.4},
    ]

    params, rmse = fit_wildfire_spread(train_samples, val_samples)
    assert "wind_coefficient" in params
    assert "temp_coefficient" in params
    assert params["wind_coefficient"] > 0.0
    assert params["temp_coefficient"] > 0.0
    assert rmse >= 0.0


def test_flood_extent_fitter_math() -> None:
    """Verify flood extent fitter math."""
    train_samples = [
        {"rainfall": 10.0, "observed": 30.0},
        {"rainfall": 20.0, "observed": 60.0},
    ]
    params, rmse = fit_flood_extent(train_samples, [])
    assert params["rainfall_coefficient"] == 3.0
    assert rmse == 0.0


def test_plume_dispersion_fitter_math() -> None:
    """Verify plume dispersion fitter math."""
    train_samples = [
        {"wind_speed": 10.0, "observed": 20.0},
        {"wind_speed": 20.0, "observed": 40.0},
    ]
    params, rmse = fit_plume_dispersion(train_samples, [])
    assert params["wind_coefficient"] == 2.0
    assert rmse == 0.0


def test_enso_forecast_percentile_math() -> None:
    """Verify ENSO threshold fitting logic."""
    train_samples = [
        {"sst_anomaly": -1.0},
        {"sst_anomaly": -0.8},
        {"sst_anomaly": -0.5},
        {"sst_anomaly": 0.0},
        {"sst_anomaly": 0.5},
        {"sst_anomaly": 0.8},
        {"sst_anomaly": 1.2},
        {"sst_anomaly": 1.5},
        {"sst_anomaly": 1.8},
        {"sst_anomaly": 2.0},
    ]
    params, err = fit_enso_forecast(train_samples, [])
    # 90th percentile of 10 items (sorted) is index 9: 2.0 (clamped to max threshold 1.5)
    assert params["el_nino_threshold"] == 1.5
    # 10th percentile is index 1: -0.8
    assert params["la_nina_threshold"] == -0.8
    assert err == 0.0


def test_outcome_extractor_parser() -> None:
    """Verify event details outcome extraction helper behaviors."""
    # Test valid matches
    assert extract_observed_outcome(
        DummyEvent("observed_spread_rate: 12.34"), "wildfire_spread"
    ) == 12.34
    assert extract_observed_outcome(
        DummyEvent("observed_flooded_area: 500.1"), "flood_extent"
    ) == 500.1
    assert extract_observed_outcome(
        DummyEvent("observed_dispersion_distance: 18.2"), "plume_dispersion"
    ) == 18.2
    assert extract_observed_outcome(
        DummyEvent("NOAA water temperature: 21.3°C"), "enso_forecast"
    ) == 21.3

    # Test malformed matches return None
    assert extract_observed_outcome(
        DummyEvent("spread_rate: missing"), "wildfire_spread"
    ) is None
    assert extract_observed_outcome(
        DummyEvent("observed_flooded_area: NaN"), "flood_extent"
    ) is None
    assert extract_observed_outcome(
        DummyEvent("some arbitrary description string"), "plume_dispersion"
    ) is None
    assert extract_observed_outcome(DummyEvent(None), "enso_forecast") is None


def test_promotion_gate_logic(tmp_path: Path) -> None:
    """Verify that parameters are promoted only if validation score is equal or better."""
    invalidate_parameter_cache()

    val_samples = [
        {"wind_speed": 10.0, "temperature": 20.0, "observed": 6.0},
    ]
    defaults = {
        "wind_coefficient": 0.4,
        "temp_coefficient": 0.1,
        "low_bound_factor": 0.7,
        "high_bound_factor": 1.3,
    }

    from unittest.mock import MagicMock
    mock_path = MagicMock()
    mock_path.resolve.return_value = mock_path
    mock_path.parent = mock_path
    mock_path.__truediv__.return_value = tmp_path

    # Redirect Path in report.py and parameter_loader.py to use tmp_path
    with patch("simulation_engine.calibration.report.Path", return_value=mock_path), \
         patch("simulation_engine.parameter_loader.Path", return_value=mock_path):

        # 1. Promote first version (new score = 0.0, which is <= baseline score
        # 0.0 when no config exists)
        new_params = {
            "wind_coefficient": 0.4,
            "temp_coefficient": 0.1,
            "low_bound_factor": 0.7,
            "high_bound_factor": 1.3,
        }
        promoted, ver, base_score, new_score = check_and_promote_parameters(
            "wildfire_spread", new_params, defaults, val_samples
        )
        assert promoted is True
        assert ver == 1
        assert (tmp_path / "simulation_parameters" / "wildfire_spread_v1.yaml").is_file()
        assert (tmp_path / "simulation_parameters" / "wildfire_spread_latest.yaml").is_file()

        # 2. Try to promote a worse candidate (should fail the promotion gate)
        worse_params = {
            "wind_coefficient": 0.9,
            "temp_coefficient": 0.5,
            "low_bound_factor": 0.7,
            "high_bound_factor": 1.3,
        }
        promoted2, ver2, base_score2, new_score2 = check_and_promote_parameters(
            "wildfire_spread", worse_params, defaults, val_samples
        )
        assert promoted2 is False
        assert new_score2 > base_score2


def test_parameter_cache_and_validation(tmp_path: Path) -> None:
    """Verify thread-safe cache invalidation, TTL updates, and strict validation checks."""
    invalidate_parameter_cache()

    defaults = {"wind_coefficient": 0.4, "temp_coefficient": 0.1}
    config_dir = tmp_path / "simulation_parameters"
    config_dir.mkdir(parents=True, exist_ok=True)
    latest_file = config_dir / "wildfire_spread_latest.yaml"

    from unittest.mock import MagicMock
    mock_path = MagicMock()
    mock_path.resolve.return_value = mock_path
    mock_path.parent = mock_path
    mock_path.__truediv__.return_value = tmp_path

    with patch("simulation_engine.parameter_loader.Path", return_value=mock_path):
        # 1. Fallback if YAML is missing
        assert load_calibrated_parameters("wildfire_spread", defaults) == defaults

        # 2. Rejects invalid formats (not dict)
        with latest_file.open("w", encoding="utf-8") as f:
            f.write("invalid YAML string structure")
        assert load_calibrated_parameters("wildfire_spread", defaults) == defaults

        # 3. Rejects missing keys
        with latest_file.open("w", encoding="utf-8") as f:
            yaml.safe_dump({"parameters": {"wind_coefficient": 0.5}}, f)
        assert load_calibrated_parameters("wildfire_spread", defaults) == defaults

        # 4. Rejects NaN / Inf values
        with latest_file.open("w", encoding="utf-8") as f:
            yaml.safe_dump(
                {"parameters": {"wind_coefficient": float("nan"), "temp_coefficient": 0.1}}, f
            )
        assert load_calibrated_parameters("wildfire_spread", defaults) == defaults

        with latest_file.open("w", encoding="utf-8") as f:
            yaml.safe_dump(
                {"parameters": {"wind_coefficient": float("inf"), "temp_coefficient": 0.1}}, f
            )
        assert load_calibrated_parameters("wildfire_spread", defaults) == defaults

        # 5. Loads valid parameters and caches them
        valid_payload = {"parameters": {"wind_coefficient": 0.8, "temp_coefficient": 0.25}}
        with latest_file.open("w", encoding="utf-8") as f:
            yaml.safe_dump(valid_payload, f)

        res = load_calibrated_parameters("wildfire_spread", defaults)
        assert res["wind_coefficient"] == 0.8
        assert res["temp_coefficient"] == 0.25

        # Modify on disk but check cache hit is served within TTL
        with latest_file.open("w", encoding="utf-8") as f:
            yaml.safe_dump({"parameters": {"wind_coefficient": 1.2, "temp_coefficient": 0.5}}, f)

        res2 = load_calibrated_parameters("wildfire_spread", defaults)
        assert res2["wind_coefficient"] == 0.8  # cached

        # Explicitly invalidate cache and verify updated values load instantly
        invalidate_parameter_cache("wildfire_spread")
        res3 = load_calibrated_parameters("wildfire_spread", defaults)
        assert res3["wind_coefficient"] == 1.2  # loaded new file


@pytest.mark.asyncio
async def test_calibration_job_integration(db_session: AsyncSession, tmp_path: Path) -> None:
    """Verify full calibration background job execution loop with database data."""
    invalidate_parameter_cache()

    # Seed ERA5 and hazard events
    dt_base = datetime.now(UTC) - timedelta(days=2)
    await db_session.execute(text("DELETE FROM hazard_events;"))
    await db_session.execute(text("DELETE FROM metrics;"))

    insert_sql = text(
        "INSERT INTO hazard_events "
        "(id, event_type, region_label, event_date, details, source, "
        "external_id, created_at) "
        "VALUES (gen_random_uuid(), :event_type, :region, :event_date, "
        ":details, :source, :external_id, now());"
    )

    # Seed ERA5 baselines
    for i in range(10):
        dt = dt_base + timedelta(days=i)
        details = (
            f"ERA5 Atmospheric Reanalysis Baseline in California on {dt.date().isoformat()}: "
            f"Mean Temp: {20.0 + i}°C, Max Wind: {10.0 + i} km/h, Precip: {5.0 + i} mm | "
            f"Provider: ECMWF ERA5 | Original ID: era5_cal_{i} | Source URL: http://fake.url"
        )
        await db_session.execute(
            insert_sql,
            {
                "event_type": "atmospheric_anomaly",
                "region": "California",
                "event_date": dt,
                "details": details,
                "source": "era5",
                "external_id": f"era5_cal_{i}",
            }
        )

    # Seed Copernicus wildfires with parsable observed_spread_rate outcome
    # matching default parameters exactly
    for i in range(10):
        dt = dt_base + timedelta(days=i)
        wind = 10.0 + i
        temp = 20.0 + i
        obs = wind * 0.4 + temp * 0.1
        details = f"Sentinel product wildfire {i} observed_spread_rate: {obs}"
        await db_session.execute(
            insert_sql,
            {
                "event_type": "wildfire_satellite",
                "region": "California",
                "event_date": dt,
                "details": details,
                "source": "copernicus",
                "external_id": f"copernicus_wf_{i}",
            }
        )

    # Seed general flood hazards with parsable observed_flooded_area outcome
    # matching default parameters exactly
    for i in range(10):
        dt = dt_base + timedelta(days=i)
        precip = 5.0 + i
        obs = precip * 3.2
        details = f"Local flood event {i} observed_flooded_area: {obs}"
        await db_session.execute(
            insert_sql,
            {
                "event_type": "flood",
                "region": "California",
                "event_date": dt,
                "details": details,
                "source": "usgs",
                "external_id": f"usgs_fld_{i}",
            }
        )

    # Seed general wind/storm hazards (plume dispersion) with parsable
    # observed_dispersion_distance outcome matching default parameters exactly
    for i in range(10):
        dt = dt_base + timedelta(days=i)
        wind = 10.0 + i
        obs = wind * 1.8
        details = f"Local storm wind {i} observed_dispersion_distance: {obs}"
        await db_session.execute(
            insert_sql,
            {
                "event_type": "storm",
                "region": "California",
                "event_date": dt,
                "details": details,
                "source": "usgs",
                "external_id": f"usgs_wnd_{i}",
            }
        )

    # Seed NOAA ocean temperature events (ENSO) alternating to prevent
    # classification mismatches
    for i in range(10):
        dt = dt_base + timedelta(days=i)
        wtemp = 18.0 if i % 2 == 0 else 22.0
        await db_session.execute(
            insert_sql,
            {
                "event_type": "marine heatwave",
                "region": "California",
                "event_date": dt,
                "details": f"NOAA station water temperature: {wtemp}°C",
                "source": "noaa",
                "external_id": f"noaa_t_{i}",
            }
        )

    await db_session.commit()

    from unittest.mock import MagicMock
    mock_path = MagicMock()
    mock_path.resolve.return_value = mock_path
    mock_path.parent = mock_path
    mock_path.__truediv__.return_value = tmp_path

    # Run the calibration job under Path-redirect mocks to write files to our tmp_path
    with patch("simulation_engine.calibration.report.Path", return_value=mock_path), \
         patch("simulation_engine.parameter_loader.Path", return_value=mock_path):

        # Mock the session factory inside calibration job to return our db_session
        class MockSessionContext:
            def __init__(self, db_session: AsyncSession) -> None:
                self.db_session = db_session
            async def __aenter__(self) -> AsyncSession:
                return self.db_session
            async def __aexit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
                await self.db_session.__aexit__(exc_type, exc_val, exc_tb)

        with patch("db.session.AsyncSessionLocal", return_value=MockSessionContext(db_session)):
            res = await _async_run_calibration_job()

            assert res["status"] == "success"
            summary = res["summary"]
            assert summary["wildfire_spread"]["status"] == "calibrated"
            assert summary["flood_extent"]["status"] == "calibrated"
            assert summary["plume_dispersion"]["status"] == "calibrated"
            assert summary["enso_forecast"]["status"] == "calibrated"

            # Check that files were written
            assert (tmp_path / "simulation_parameters" / "wildfire_spread_latest.yaml").is_file()
            assert (tmp_path / "simulation_parameters" / "flood_extent_latest.yaml").is_file()
            assert (tmp_path / "simulation_parameters" / "plume_dispersion_latest.yaml").is_file()
            assert (tmp_path / "simulation_parameters" / "enso_forecast_latest.yaml").is_file()

            # Ensure we can load them successfully using the loader
            from simulation_engine.parameter_loader import load_calibrated_parameters
            defaults = {"wind_coefficient": 99.0}
            cal_params = load_calibrated_parameters("wildfire_spread", defaults)
            assert cal_params != defaults
            assert cal_params["wind_coefficient"] == 0.4
