"""Data structures and schemas for scheduled hazard event ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class HazardEventRecord:
    """Represents a raw ingested hazard event record prior to database persistence."""

    source: str
    external_id: str
    event_type: str
    region_label: str
    point: tuple[float, float]  # (latitude, longitude)
    event_date: datetime
    details: str | None = None
