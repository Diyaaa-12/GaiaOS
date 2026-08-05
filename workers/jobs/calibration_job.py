"""Worker job for scheduled simulation model calibration."""

from __future__ import annotations

import asyncio
import random
import re
import time
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

import db.session as db_session
from config.settings import get_settings
from logging_config import configure_logging, get_logger
from metrics.collector import emit, persist_metric
from metrics.events import CalibrationCompleted
from simulation_engine.calibration.constants import (
    CALIBRATION_RANDOM_SEED,
    MIN_CALIBRATION_SAMPLES,
    TRAIN_VALIDATION_SPLIT_RATIO,
)
from simulation_engine.calibration.fit_enso_forecast import fit_enso_forecast
from simulation_engine.calibration.fit_flood_extent import fit_flood_extent
from simulation_engine.calibration.fit_plume_dispersion import fit_plume_dispersion
from simulation_engine.calibration.fit_wildfire_spread import fit_wildfire_spread
from simulation_engine.calibration.outcome_extractor import extract_observed_outcome
from simulation_engine.calibration.report import check_and_promote_parameters

_log = get_logger(__name__)


def parse_era5_details(details: str) -> tuple[float | None, float | None, float | None]:
    """Extract temperature, wind speed, and precipitation from ERA5 details string."""
    try:
        temp_match = re.search(r"Mean Temp:\s*([-0-9.]+)", details)
        wind_match = re.search(r"Max Wind:\s*([-0-9.]+)", details)
        precip_match = re.search(r"Precip:\s*([-0-9.]+)", details)

        temp = float(temp_match.group(1)) if temp_match else None
        wind = float(wind_match.group(1)) if wind_match else None
        precip = float(precip_match.group(1)) if precip_match else None
        return temp, wind, precip
    except Exception:
        return None, None, None


async def _calibrate_wildfire(
    session: AsyncSession,
    copernicus_events: list[Any],
    era5_events: list[Any],
    summary: dict[str, Any],
) -> None:
    """Calibrate WildfireSpreadModel coefficients against historical outcomes."""
    wildfire_samples = []
    for cop in copernicus_events:
        cop_date = cop.event_date.date()
        matching_era5 = [
            e for e in era5_events
            if e.event_date.date() == cop_date and e.region_label == cop.region_label
        ]
        if matching_era5:
            temp, wind, _ = parse_era5_details(matching_era5[0].details or "")
            if temp is not None and wind is not None:
                obs = extract_observed_outcome(cop, "wildfire_spread")
                if obs is not None:
                    wildfire_samples.append({
                        "wind_speed": wind,
                        "temperature": temp,
                        "observed": obs,
                    })

    if len(wildfire_samples) >= MIN_CALIBRATION_SAMPLES:
        random.Random(CALIBRATION_RANDOM_SEED).shuffle(wildfire_samples)
        split = int(len(wildfire_samples) * TRAIN_VALIDATION_SPLIT_RATIO)
        train = wildfire_samples[:split]
        val = wildfire_samples[split:]
        defaults = {
            "wind_coefficient": 0.4,
            "temp_coefficient": 0.1,
            "low_bound_factor": 0.7,
            "high_bound_factor": 1.3,
        }
        fitted_params, rmse = fit_wildfire_spread(train, val)
        promoted, ver, base_score, new_score = check_and_promote_parameters(
            "wildfire_spread", fitted_params, defaults, val
        )
        summary["wildfire_spread"] = {
            "status": "calibrated",
            "promoted": promoted,
            "version": ver,
            "rmse": float(new_score),
        }
        if promoted:
            evt = CalibrationCompleted("wildfire_spread", True, ver, new_score)
            emit(evt)
            await persist_metric(session, evt)
    else:
        _log.warning(
            "simulation.calibration.skipped",
            model="wildfire_spread",
            reason="insufficient_data",
        )
        summary["wildfire_spread"] = {
            "status": "skipped",
            "reason": "insufficient_data",
        }


async def _calibrate_flood(
    session: AsyncSession,
    general_hazards: list[Any],
    era5_events: list[Any],
    summary: dict[str, Any],
) -> None:
    """Calibrate FloodExtentModel rainfall_coefficient against historical outcomes."""
    flood_samples = []
    flood_hazards = [h for h in general_hazards if "flood" in (h.event_type or "").lower()]
    for fld in flood_hazards:
        fld_date = fld.event_date.date()
        matching_era5 = [
            e for e in era5_events
            if e.event_date.date() == fld_date and e.region_label == fld.region_label
        ]
        if matching_era5:
            _, _, precip = parse_era5_details(matching_era5[0].details or "")
            if precip is not None and precip > 0:
                obs = extract_observed_outcome(fld, "flood_extent")
                if obs is not None:
                    flood_samples.append({
                        "rainfall": precip,
                        "observed": obs,
                    })

    if len(flood_samples) >= MIN_CALIBRATION_SAMPLES:
        random.Random(CALIBRATION_RANDOM_SEED).shuffle(flood_samples)
        split = int(len(flood_samples) * TRAIN_VALIDATION_SPLIT_RATIO)
        train = flood_samples[:split]
        val = flood_samples[split:]
        defaults = {
            "rainfall_coefficient": 3.2,
            "low_bound_factor": 2.8,
            "high_bound_factor": 3.6,
        }
        fitted_params, rmse = fit_flood_extent(train, val)
        promoted, ver, base_score, new_score = check_and_promote_parameters(
            "flood_extent", fitted_params, defaults, val
        )
        summary["flood_extent"] = {
            "status": "calibrated",
            "promoted": promoted,
            "version": ver,
            "rmse": float(new_score),
        }
        if promoted:
            evt = CalibrationCompleted("flood_extent", True, ver, new_score)
            emit(evt)
            await persist_metric(session, evt)
    else:
        _log.warning(
            "simulation.calibration.skipped",
            model="flood_extent",
            reason="insufficient_data",
        )
        summary["flood_extent"] = {
            "status": "skipped",
            "reason": "insufficient_data",
        }


async def _calibrate_plume(
    session: AsyncSession,
    general_hazards: list[Any],
    era5_events: list[Any],
    summary: dict[str, Any],
) -> None:
    """Calibrate PlumeDispersionModel wind_coefficient against historical outcomes."""
    plume_samples = []
    wind_hazards = [
        h for h in general_hazards
        if any(
            k in (h.event_type or "").lower()
            for k in ("wind", "storm", "hurricane", "tornado")
        )
    ]
    for wnd in wind_hazards:
        wnd_date = wnd.event_date.date()
        matching_era5 = [
            e for e in era5_events
            if e.event_date.date() == wnd_date and e.region_label == wnd.region_label
        ]
        if matching_era5:
            _, wind, _ = parse_era5_details(matching_era5[0].details or "")
            if wind is not None and wind > 0:
                obs = extract_observed_outcome(wnd, "plume_dispersion")
                if obs is not None:
                    plume_samples.append({
                        "wind_speed": wind,
                        "observed": obs,
                    })

    if len(plume_samples) >= MIN_CALIBRATION_SAMPLES:
        random.Random(CALIBRATION_RANDOM_SEED).shuffle(plume_samples)
        split = int(len(plume_samples) * TRAIN_VALIDATION_SPLIT_RATIO)
        train = plume_samples[:split]
        val = plume_samples[split:]
        defaults = {
            "wind_coefficient": 1.8,
            "low_bound_factor": 1.5,
            "high_bound_factor": 2.1,
        }
        fitted_params, rmse = fit_plume_dispersion(train, val)
        promoted, ver, base_score, new_score = check_and_promote_parameters(
            "plume_dispersion", fitted_params, defaults, val
        )
        summary["plume_dispersion"] = {
            "status": "calibrated",
            "promoted": promoted,
            "version": ver,
            "rmse": float(new_score),
        }
        if promoted:
            evt = CalibrationCompleted("plume_dispersion", True, ver, new_score)
            emit(evt)
            await persist_metric(session, evt)
    else:
        _log.warning(
            "simulation.calibration.skipped",
            model="plume_dispersion",
            reason="insufficient_data",
        )
        summary["plume_dispersion"] = {
            "status": "skipped",
            "reason": "insufficient_data",
        }


async def _calibrate_enso(
    session: AsyncSession,
    noaa_events: list[Any],
    summary: dict[str, Any],
) -> None:
    """Calibrate ENSOForecastModel thresholds using real water temperature observations."""
    enso_samples = []
    for noaa in noaa_events:
        obs = extract_observed_outcome(noaa, "enso_forecast")
        if obs is not None:
            # Compute anomaly relative to an assumed climatology baseline of 20°C
            sst_anomaly = obs - 20.0
            enso_samples.append({"sst_anomaly": sst_anomaly})

    if len(enso_samples) >= MIN_CALIBRATION_SAMPLES:
        random.Random(CALIBRATION_RANDOM_SEED).shuffle(enso_samples)
        split = int(len(enso_samples) * TRAIN_VALIDATION_SPLIT_RATIO)
        train = enso_samples[:split]
        val = enso_samples[split:]
        defaults = {
            "el_nino_threshold": 0.5,
            "la_nina_threshold": -0.5,
            "low_bound_offset": -0.2,
            "high_bound_offset": 0.2,
        }
        fitted_params, err_rate = fit_enso_forecast(train, val)
        promoted, ver, base_score, new_score = check_and_promote_parameters(
            "enso_forecast", fitted_params, defaults, val
        )
        summary["enso_forecast"] = {
            "status": "calibrated",
            "promoted": promoted,
            "version": ver,
            "error_rate": float(new_score),
        }
        if promoted:
            evt = CalibrationCompleted("enso_forecast", True, ver, new_score)
            emit(evt)
            await persist_metric(session, evt)
    else:
        _log.warning(
            "simulation.calibration.skipped",
            model="enso_forecast",
            reason="insufficient_data",
        )
        summary["enso_forecast"] = {
            "status": "skipped",
            "reason": "insufficient_data",
        }


async def _async_run_calibration_job() -> dict[str, Any]:
    """Execute the simulation calibration process across all models."""
    start_time = time.perf_counter()

    if db_session.AsyncSessionLocal is None:
        db_session.init_engine()
        if db_session.AsyncSessionLocal is None:
            raise RuntimeError("Database session factory is not initialised.")

    summary: dict[str, Any] = {}

    async with db_session.AsyncSessionLocal() as session:
        # Gather all hazard events and ERA5 baselines
        events_res = await session.execute(
            text(
                "SELECT source, event_type, region_label, event_date, details, external_id "
                "FROM hazard_events ORDER BY event_date ASC;"
            )
        )
        all_events = events_res.fetchall()

        copernicus_events = [e for e in all_events if e.source == "copernicus"]
        era5_events = [e for e in all_events if e.source == "era5"]
        noaa_events = [e for e in all_events if e.source == "noaa"]
        general_hazards = [e for e in all_events if e.source not in ("copernicus", "era5", "noaa")]

        _log.info(
            "simulation.calibration.data_loaded",
            copernicus_count=len(copernicus_events),
            era5_count=len(era5_events),
            noaa_count=len(noaa_events),
            general_count=len(general_hazards),
        )

        # Calibrate models sequentially
        await _calibrate_wildfire(session, copernicus_events, era5_events, summary)
        await _calibrate_flood(session, general_hazards, era5_events, summary)
        await _calibrate_plume(session, general_hazards, era5_events, summary)
        await _calibrate_enso(session, noaa_events, summary)

        await session.commit()

    duration_ms = int((time.perf_counter() - start_time) * 1000)
    _log.info("simulation.calibration.job_completed", duration_ms=duration_ms, summary=summary)

    return {
        "status": "success",
        "duration_ms": duration_ms,
        "summary": summary,
    }


def run_calibration_job() -> dict[str, Any]:
    """RQ Worker entrypoint function for scheduled simulation calibration."""
    settings = get_settings()
    configure_logging(settings)
    return asyncio.run(_async_run_calibration_job())
