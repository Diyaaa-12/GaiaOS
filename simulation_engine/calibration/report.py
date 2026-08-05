"""Validation report and promotion gate for simulation calibration parameters."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import yaml  # type: ignore

from logging_config import get_logger
from simulation_engine.calibration.version_manager import next_parameter_version
from simulation_engine.parameter_loader import (
    invalidate_parameter_cache,
    load_calibrated_parameters,
)

_log = get_logger(__name__)


def evaluate_parameters(
    model_name: str,
    parameters: dict[str, float],
    val_samples: list[dict[str, float]],
) -> float:
    """Evaluate a parameter set on validation samples and return its error score.

    Lower error score is better. For wildfire, flood, and plume, this is RMSE.
    For ENSO, this is classification error rate.
    """
    if not val_samples:
        return 0.0

    if model_name == "wildfire_spread":
        w = parameters.get("wind_coefficient", 0.4)
        t = parameters.get("temp_coefficient", 0.1)
        se = sum(
            (s["observed"] - (s["wind_speed"] * w + s["temperature"] * t)) ** 2
            for s in val_samples
        )
        return (se / len(val_samples)) ** 0.5

    elif model_name == "flood_extent":
        r = parameters.get("rainfall_coefficient", 3.2)
        se = sum((s["observed"] - (s["rainfall"] * r)) ** 2 for s in val_samples)
        return (se / len(val_samples)) ** 0.5

    elif model_name == "plume_dispersion":
        w = parameters.get("wind_coefficient", 1.8)
        se = sum((s["observed"] - (s["wind_speed"] * w)) ** 2 for s in val_samples)
        return (se / len(val_samples)) ** 0.5

    elif model_name == "enso_forecast":
        nino = parameters.get("el_nino_threshold", 0.5)
        nina = parameters.get("la_nina_threshold", -0.5)
        mismatches = 0
        for s in val_samples:
            anom = s["sst_anomaly"]
            gt = (
                "El Niño" if anom >= 0.5 else ("La Niña" if anom <= -0.5 else "Neutral")
            )
            pred = (
                "El Niño" if anom >= nino else ("La Niña" if anom <= nina else "Neutral")
            )
            if pred != gt:
                mismatches += 1
        return mismatches / len(val_samples)

    return 999.0


def check_and_promote_parameters(
    model_name: str,
    new_params: dict[str, float],
    defaults: dict[str, float],
    val_samples: list[dict[str, float]],
) -> tuple[bool, int, float, float]:
    """Compare new vs current parameters on validation data.

    If new parameters perform better than or equal to current parameters,
    saves the versioned YAML, invalidates parameters cache, and updates
    latest.yaml pointer file.
    Returns (promoted, new_version, current_score, new_score).
    """
    config_dir = Path(__file__).resolve().parent.parent.parent / "config" / "simulation_parameters"
    config_dir.mkdir(parents=True, exist_ok=True)

    current_params = load_calibrated_parameters(model_name, defaults)

    # Compute validation scores (lower is better)
    current_score = evaluate_parameters(model_name, current_params, val_samples)
    new_score = evaluate_parameters(model_name, new_params, val_samples)

    previous_ver = next_parameter_version(model_name, config_dir) - 1
    new_version = previous_ver + 1

    # Promotion Gate: new_score must be <= current_score
    promoted = new_score <= current_score

    if promoted:
        # Write immutable versioned file
        ver_file = config_dir / f"{model_name}_v{new_version}.yaml"
        latest_file = config_dir / f"{model_name}_latest.yaml"

        payload = {
            "model_name": model_name,
            "version": new_version,
            "fitted_at": datetime.now(UTC).isoformat(),
            "validation_report": {
                "sample_count": len(val_samples),
                "baseline_score": float(current_score),
                "promoted_score": float(new_score),
            },
            "parameters": new_params,
        }

        # Write files using pathlib
        with ver_file.open("w", encoding="utf-8") as f:
            yaml.safe_dump(payload, f, default_flow_style=False)

        with latest_file.open("w", encoding="utf-8") as f:
            yaml.safe_dump(payload, f, default_flow_style=False)

        # Invalidate parameters cache immediately to refresh loaded parameters
        invalidate_parameter_cache(model_name)

        _log.info(
            "simulation.calibration.promoted",
            model_name=model_name,
            previous_version=previous_ver,
            candidate_version=new_version,
            baseline_validation_score=current_score,
            candidate_validation_score=new_score,
            sample_count=len(val_samples),
            reason=(
                "candidate validation score is better than or "
                "equal to baseline validation score"
            ),
        )
    else:
        _log.warning(
            "simulation.calibration.rejected",
            model_name=model_name,
            previous_version=previous_ver,
            candidate_version=new_version,
            baseline_validation_score=current_score,
            candidate_validation_score=new_score,
            sample_count=len(val_samples),
            reason=(
                "candidate validation score is worse than "
                "baseline validation score"
            ),
        )

    return promoted, new_version, current_score, new_score
