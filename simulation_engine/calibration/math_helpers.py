"""Mathematical helper utilities for simulation calibration."""

from __future__ import annotations

import math


def compute_rmse(predictions: list[float], observed: list[float]) -> float:
    """Compute Root Mean Squared Error between predictions and observations."""
    if not predictions or not observed or len(predictions) != len(observed):
        return 999.0

    se = sum((p - o) ** 2 for p, o in zip(predictions, observed, strict=True))
    return math.sqrt(se / len(predictions))


def compute_std_dev(residuals: list[float]) -> float:
    """Compute standard deviation of residuals."""
    if not residuals:
        return 0.0

    mean_res = sum(residuals) / len(residuals)
    variance = sum((r - mean_res) ** 2 for r in residuals) / len(residuals)
    return math.sqrt(variance)


def compute_bounds_factors(
    mean_pred: float,
    std_dev: float,
    default_low: float,
    default_high: float,
) -> tuple[float, float]:
    """Calculate low/high bound multipliers for uncertainty bands."""
    if mean_pred > 0.1:
        low = max(0.1, min(0.95, (mean_pred - std_dev) / mean_pred))
        high = max(1.05, min(3.0, (mean_pred + std_dev) / mean_pred))
        return low, high

    return default_low, default_high
