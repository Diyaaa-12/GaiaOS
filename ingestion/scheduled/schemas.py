"""Data structures and schemas for scheduled hazard event ingestion."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


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


@dataclass
class PaperRecord:
    """Represents a raw ingested scientific paper record from open-access sources."""

    source_id: str
    title: str
    authors: list[str]
    published_date: datetime
    abstract_and_body: str
    source_url: str
    extra_metadata: dict[str, Any] = field(default_factory=dict)
