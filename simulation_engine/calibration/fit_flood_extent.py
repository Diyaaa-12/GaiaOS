"""Parameter fitting implementation for FloodExtentModel."""

from __future__ import annotations

from simulation_engine.calibration.math_helpers import (
    compute_bounds_factors,
    compute_rmse,
    compute_std_dev,
)

# Default baseline and sanity limit constants
DEFAULT_RAIN_COEFF = 3.2
DEFAULT_LOW_BOUND_ABS = 2.8
DEFAULT_HIGH_BOUND_ABS = 3.6

MIN_RAIN_COEFF_LIMIT = 0.1
MAX_RAIN_COEFF_LIMIT = 10.0


def fit_flood_extent(
    train_samples: list[dict[str, float]],
    val_samples: list[dict[str, float]],
) -> tuple[dict[str, float], float]:
    """Fit rainfall_coefficient using closed-form single parameter least squares."""
    defaults = {
        "rainfall_coefficient": DEFAULT_RAIN_COEFF,
        "low_bound_factor": DEFAULT_LOW_BOUND_ABS,
        "high_bound_factor": DEFAULT_HIGH_BOUND_ABS,
    }

    if not train_samples:
        return defaults, 999.0

    sum_xy = sum(s["rainfall"] * s["observed"] for s in train_samples)
    sum_x2 = sum(s["rainfall"] ** 2 for s in train_samples)

    if sum_x2 < 1e-6:
        return defaults, 999.0

    rain_coeff = sum_xy / sum_x2

    # Clamp coefficient to sanity limits
    rain_coeff = max(MIN_RAIN_COEFF_LIMIT, min(MAX_RAIN_COEFF_LIMIT, rain_coeff))

    # Calculate residuals & std dev
    preds = [s["rainfall"] * rain_coeff for s in train_samples]
    residuals = [s["observed"] - p for s, p in zip(train_samples, preds, strict=True)]
    std_dev = compute_std_dev(residuals)

    mean_pred = sum(preds) / len(train_samples)
    rel_default_low = DEFAULT_LOW_BOUND_ABS / DEFAULT_RAIN_COEFF
    rel_default_high = DEFAULT_HIGH_BOUND_ABS / DEFAULT_RAIN_COEFF

    rel_low, rel_high = compute_bounds_factors(
        mean_pred, std_dev, rel_default_low, rel_default_high
    )

    params = {
        "rainfall_coefficient": float(round(rain_coeff, 4)),
        "low_bound_factor": float(round(rel_low * rain_coeff, 4)),
        "high_bound_factor": float(round(rel_high * rain_coeff, 4)),
    }

    if val_samples:
        val_preds = [s["rainfall"] * rain_coeff for s in val_samples]
        val_obs = [s["observed"] for s in val_samples]
        rmse = compute_rmse(val_preds, val_obs)
    else:
        rmse = 0.0

    return params, rmse
