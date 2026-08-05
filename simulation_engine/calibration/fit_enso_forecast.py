"""Parameter fitting implementation for ENSOForecastModel."""

from __future__ import annotations

from simulation_engine.calibration.math_helpers import compute_std_dev

# Default baseline and sanity limit constants
DEFAULT_NINO_THRESH = 0.5
DEFAULT_NINA_THRESH = -0.5
DEFAULT_LOW_OFFSET = -0.2
DEFAULT_HIGH_OFFSET = 0.2

MIN_NINO_LIMIT = 0.2
MAX_NINO_LIMIT = 1.5
MIN_NINA_LIMIT = -1.5
MAX_NINA_LIMIT = -0.2


def fit_enso_forecast(
    train_samples: list[dict[str, float]],
    val_samples: list[dict[str, float]],
) -> tuple[dict[str, float], float]:
    """Fit el_nino_threshold and la_nina_threshold using percentile cutoffs."""
    defaults = {
        "el_nino_threshold": DEFAULT_NINO_THRESH,
        "la_nina_threshold": DEFAULT_NINA_THRESH,
        "low_bound_offset": DEFAULT_LOW_OFFSET,
        "high_bound_offset": DEFAULT_HIGH_OFFSET,
    }

    if len(train_samples) < 5:
        return defaults, 1.0

    anomalies = sorted(s["sst_anomaly"] for s in train_samples)
    n = len(anomalies)

    # 90th percentile for El Nino, 10th percentile for La Nina
    el_nino_val = anomalies[int(n * 0.9)]
    la_nina_val = anomalies[int(n * 0.1)]

    # Clamp thresholds to sanity limits
    el_nino_threshold = max(MIN_NINO_LIMIT, min(MAX_NINO_LIMIT, el_nino_val))
    la_nina_threshold = max(MIN_NINA_LIMIT, min(MAX_NINA_LIMIT, la_nina_val))

    # Calculate standard deviation of anomalies for bounds offset
    mean_anom = sum(anomalies) / n
    std_dev = compute_std_dev([a - mean_anom for a in anomalies])

    low_offset = -max(0.05, min(1.0, std_dev))
    high_offset = max(0.05, min(1.0, std_dev))

    params = {
        "el_nino_threshold": float(round(el_nino_threshold, 4)),
        "la_nina_threshold": float(round(la_nina_threshold, 4)),
        "low_bound_offset": float(round(low_offset, 4)),
        "high_bound_offset": float(round(high_offset, 4)),
    }

    # Evaluate validation error rate (1.0 - classification accuracy)
    if val_samples:
        mismatches = 0
        for s in val_samples:
            anom = s["sst_anomaly"]
            # Ground truth classification using standard baseline
            if anom >= 0.5:
                gt_state = "El Niño"
            elif anom <= -0.5:
                gt_state = "La Niña"
            else:
                gt_state = "Neutral"

            # Predicted classification using new thresholds
            if anom >= el_nino_threshold:
                pred_state = "El Niño"
            elif anom <= la_nina_threshold:
                pred_state = "La Niña"
            else:
                pred_state = "Neutral"

            if pred_state != gt_state:
                mismatches += 1

        error_rate = mismatches / len(val_samples)
    else:
        error_rate = 0.0

    return params, error_rate
