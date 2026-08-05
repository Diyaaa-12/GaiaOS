"""Helper to load calibrated simulation parameters from versioned config files."""

from __future__ import annotations

import math
import threading
import time
from pathlib import Path
from typing import Any

import yaml  # type: ignore

from logging_config import get_logger
from simulation_engine.calibration.constants import CACHE_TTL_SECONDS

_log = get_logger(__name__)

# Thread-safe cache: model_name -> (last_checked_time, cached_mtime, params_dict)
_parameter_cache: dict[str, tuple[float, float, dict[str, float]]] = {}
_cache_lock = threading.Lock()


def validate_parameters_yaml(data: Any, required_keys: list[str]) -> bool:
    """Verify that loaded config data adheres to strict schema and numeric limits."""
    if not isinstance(data, dict):
        _log.warning("simulation.parameters.validation_failed_not_dict")
        return False

    params = data.get("parameters")
    if not isinstance(params, dict):
        _log.warning("simulation.parameters.validation_failed_no_parameters_field")
        return False

    for k in required_keys:
        if k not in params:
            _log.warning("simulation.parameters.validation_failed_missing_key", missing_key=k)
            return False
        val = params[k]
        # Reject non-numeric, NaN, and Inf values
        if not isinstance(val, (int, float)) or not math.isfinite(val):
            _log.warning("simulation.parameters.validation_failed_invalid_value", key=k, value=val)
            return False

    return True


def load_calibrated_parameters(model_name: str, defaults: dict[str, float]) -> dict[str, float]:
    """Load the latest active parameters for a model, using a thread-safe, TTL-based cache.

    If the config is missing or validation fails, safely returns defaults.
    """
    config_dir = Path(__file__).resolve().parent.parent / "config" / "simulation_parameters"
    latest_file = config_dir / f"{model_name}_latest.yaml"

    now = time.time()

    # 1. Thread-safe fast path cache hit (skip file stat completely if within TTL)
    with _cache_lock:
        if model_name in _parameter_cache:
            last_checked, cached_mtime, cached_params = _parameter_cache[model_name]
            if now - last_checked <= CACHE_TTL_SECONDS:
                return cached_params

    # 2. Disk validation check (either cache miss or expired TTL)
    if not latest_file.is_file():
        return defaults

    try:
        mtime = latest_file.stat().st_mtime

        with _cache_lock:
            # If the file mtime hasn't changed, reuse cache and bump checking timestamp
            if model_name in _parameter_cache:
                _, cached_mtime, cached_params = _parameter_cache[model_name]
                if mtime == cached_mtime:
                    _parameter_cache[model_name] = (now, mtime, cached_params)
                    return cached_params

        # 3. Reload from file and validate
        with open(latest_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        required_keys = list(defaults.keys())
        if not validate_parameters_yaml(data, required_keys):
            return defaults

        params: dict[str, float] = {}
        for k in required_keys:
            params[k] = float(data["parameters"][k])

        with _cache_lock:
            _parameter_cache[model_name] = (now, mtime, params)

        return params

    except Exception as exc:
        _log.warning(
            "simulation.parameters.load_failed",
            model_name=model_name,
            error=str(exc),
        )
        return defaults


def invalidate_parameter_cache(model_name: str | None = None) -> None:
    """Thread-safe cache invalidation for model parameters.

    If model_name is None, invalidates the entire cache.
    """
    with _cache_lock:
        if model_name is None:
            _parameter_cache.clear()
            _log.info("simulation.parameters.cache_invalidated_all")
        else:
            _parameter_cache.pop(model_name, None)
            _log.info("simulation.parameters.cache_invalidated_model", model_name=model_name)
