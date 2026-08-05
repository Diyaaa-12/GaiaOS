"""Parameter fitting implementation for PlumeDispersionModel."""

from __future__ import annotations

from simulation_engine.calibration.math_helpers import (
    compute_bounds_factors,
    compute_rmse,
    compute_std_dev,
)

# Default baseline and sanity limit constants
DEFAULT_WIND_COEFF = 1.8
DEFAULT_LOW_BOUND_ABS = 1.5
DEFAULT_HIGH_BOUND_ABS = 2.1

MIN_WIND_COEFF_LIMIT = 0.1
MAX_WIND_COEFF_LIMIT = 10.0


def fit_plume_dispersion(
    train_samples: list[dict[str, float]],
    val_samples: list[dict[str, float]],
) -> tuple[dict[str, float], float]:
    """Fit wind_coefficient using closed-form single parameter least squares."""
    defaults = {
        "wind_coefficient": DEFAULT_WIND_COEFF,
        "low_bound_factor": DEFAULT_LOW_BOUND_ABS,
        "high_bound_factor": DEFAULT_HIGH_BOUND_ABS,
    }

    if not train_samples:
        return defaults, 999.0

    sum_xy = sum(s["wind_speed"] * s["observed"] for s in train_samples)
    sum_x2 = sum(s["wind_speed"] ** 2 for s in train_samples)

    if sum_x2 < 1e-6:
        return defaults, 999.0

    wind_coeff = sum_xy / sum_x2

    # Clamp coefficient to sanity limits
    wind_coeff = max(MIN_WIND_COEFF_LIMIT, min(MAX_WIND_COEFF_LIMIT, wind_coeff))

    # Calculate residuals & std dev
    preds = [s["wind_speed"] * wind_coeff for s in train_samples]
    residuals = [s["observed"] - p for s, p in zip(train_samples, preds, strict=True)]
    std_dev = compute_std_dev(residuals)

    mean_pred = sum(preds) / len(train_samples)
    rel_default_low = DEFAULT_LOW_BOUND_ABS / DEFAULT_WIND_COEFF
    rel_default_high = DEFAULT_HIGH_BOUND_ABS / DEFAULT_WIND_COEFF

    rel_low, rel_high = compute_bounds_factors(
        mean_pred, std_dev, rel_default_low, rel_default_high
    )

    params = {
        "wind_coefficient": float(round(wind_coeff, 4)),
        "low_bound_factor": float(round(rel_low * wind_coeff, 4)),
        "high_bound_factor": float(round(rel_high * wind_coeff, 4)),
    }

    if val_samples:
        val_preds = [s["wind_speed"] * wind_coeff for s in val_samples]
        val_obs = [s["observed"] for s in val_samples]
        rmse = compute_rmse(val_preds, val_obs)
    else:
        rmse = 0.0

    return params, rmse
