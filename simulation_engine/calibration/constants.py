"""Centralized constants for simulation calibration."""

from __future__ import annotations

# Minimum samples required to run calibration for any model
MIN_CALIBRATION_SAMPLES: int = 5

# Ratio of samples allocated to training (vs validation)
TRAIN_VALIDATION_SPLIT_RATIO: float = 0.8

# Fixed random seed for deterministic dataset shuffling
CALIBRATION_RANDOM_SEED: int = 42

# Default interval in days between automated calibration runs
DEFAULT_CALIBRATION_INTERVAL_DAYS: int = 30

# In-memory parameter cache Time-To-Live in seconds
CACHE_TTL_SECONDS: float = 30.0
