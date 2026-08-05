"""Event outcome parsing abstraction for model calibration."""

from __future__ import annotations

import re
from typing import Protocol


class ObservableEvent(Protocol):
    """Protocol representing a hazard or atmospheric observation event with details."""

    details: str | None


def extract_observed_outcome(event: ObservableEvent, outcome_type: str) -> float | None:
    """Parse real historical outcomes from event detail descriptions.

    Isolates regex extraction logic from core calibration engines.
    """
    details = event.details
    if not details:
        return None

    try:
        if outcome_type == "wildfire_spread":
            match = re.search(r"observed_spread_rate:\s*([-0-9.]+)", details)
            return float(match.group(1)) if match else None

        elif outcome_type == "flood_extent":
            match = re.search(r"observed_flooded_area:\s*([-0-9.]+)", details)
            return float(match.group(1)) if match else None

        elif outcome_type == "plume_dispersion":
            match = re.search(r"observed_dispersion_distance:\s*([-0-9.]+)", details)
            return float(match.group(1)) if match else None

        elif outcome_type == "enso_forecast":
            match = re.search(r"water temperature:\s*([-0-9.]+)", details)
            return float(match.group(1)) if match else None

    except (ValueError, IndexError):
        return None

    return None
