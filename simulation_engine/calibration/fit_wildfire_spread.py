"""Parameter fitting implementation for WildfireSpreadModel."""

from __future__ import annotations

from simulation_engine.calibration.math_helpers import (
    compute_bounds_factors,
    compute_rmse,
    compute_std_dev,
)

# Constants for default values and sanity limits
DEFAULT_WIND_COEFF = 0.4
DEFAULT_TEMP_COEFF = 0.1
DEFAULT_LOW_BOUND_FACTOR = 0.7
DEFAULT_HIGH_BOUND_FACTOR = 1.3

MIN_WIND_COEFF_LIMIT = 0.01
MAX_WIND_COEFF_LIMIT = 2.0
MIN_TEMP_COEFF_LIMIT = 0.01
MAX_TEMP_COEFF_LIMIT = 1.0


def fit_wildfire_spread(
    train_samples: list[dict[str, float]],
    val_samples: list[dict[str, float]],
) -> tuple[dict[str, float], float]:
    """Fit wind_coefficient and temp_coefficient using closed-form least squares."""
    defaults = {
        "wind_coefficient": DEFAULT_WIND_COEFF,
        "temp_coefficient": DEFAULT_TEMP_COEFF,
        "low_bound_factor": DEFAULT_LOW_BOUND_FACTOR,
        "high_bound_factor": DEFAULT_HIGH_BOUND_FACTOR,
    }

    if len(train_samples) < 2:
        return defaults, 999.0

    # Solve A * beta = B
    sum_w2 = sum(s["wind_speed"] ** 2 for s in train_samples)
    sum_t2 = sum(s["temperature"] ** 2 for s in train_samples)
    sum_wt = sum(s["wind_speed"] * s["temperature"] for s in train_samples)
    sum_wy = sum(s["wind_speed"] * s["observed"] for s in train_samples)
    sum_ty = sum(s["temperature"] * s["observed"] for s in train_samples)

    det = sum_w2 * sum_t2 - (sum_wt ** 2)
    if abs(det) < 1e-6:
        return defaults, 999.0

    wind_coeff = (sum_t2 * sum_wy - sum_wt * sum_ty) / det
    temp_coeff = (sum_w2 * sum_ty - sum_wt * sum_wy) / det

    # Clamp coefficients to sanity limits
    wind_coeff = max(MIN_WIND_COEFF_LIMIT, min(MAX_WIND_COEFF_LIMIT, wind_coeff))
    temp_coeff = max(MIN_TEMP_COEFF_LIMIT, min(MAX_TEMP_COEFF_LIMIT, temp_coeff))

    # Compute residuals & std dev
    preds = [
        s["wind_speed"] * wind_coeff + s["temperature"] * temp_coeff
        for s in train_samples
    ]
    residuals = [s["observed"] - p for s, p in zip(train_samples, preds, strict=True)]
    std_dev = compute_std_dev(residuals)

    mean_pred = sum(preds) / len(train_samples)
    low_factor, high_factor = compute_bounds_factors(
        mean_pred, std_dev, DEFAULT_LOW_BOUND_FACTOR, DEFAULT_HIGH_BOUND_FACTOR
    )

    params = {
        "wind_coefficient": float(round(wind_coeff, 4)),
        "temp_coefficient": float(round(temp_coeff, 4)),
        "low_bound_factor": float(round(low_factor, 4)),
        "high_bound_factor": float(round(high_factor, 4)),
    }

    if val_samples:
        val_preds = [
            s["wind_speed"] * wind_coeff + s["temperature"] * temp_coeff
            for s in val_samples
        ]
        val_obs = [s["observed"] for s in val_samples]
        rmse = compute_rmse(val_preds, val_obs)
    else:
        rmse = 0.0

    return params, rmse
