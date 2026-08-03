"""Historical hazard event source adapter for Copernicus Sentinel satellite wildfire metadata."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from ingestion.scheduled.schemas import HazardEventRecord
from logging_config import get_logger
from tools.copernicus_sentinel.client import CopernicusSentinelClient

_log = get_logger(__name__)

# Standard monitoring bounding boxes (e.g. California, Southern Europe, SE Asia)
DEFAULT_BBOXES = [
    {"name": "California", "min_x": -124.4, "min_y": 32.5, "max_x": -114.1, "max_y": 42.0},
    {"name": "Mediterranean", "min_x": -10.0, "min_y": 35.0, "max_x": 30.0, "max_y": 45.0},
]


async def fetch_recent_copernicus_events(
    since: datetime | None = None,
) -> list[HazardEventRecord]:
    """Fetch recent Copernicus Sentinel satellite wildfire product metadata.

    Maps product metadata to HazardEventRecord with full source attribution in details.
    """
    now = datetime.now(UTC)
    start_dt = since or (now - timedelta(days=7))

    _log.info("ingestion.source.copernicus.fetching", since=start_dt.isoformat())

    client = CopernicusSentinelClient()
    records: list[HazardEventRecord] = []

    for bbox in DEFAULT_BBOXES:
        try:
            result = await client.get_wildfire_products(
                min_x=bbox["min_x"],
                min_y=bbox["min_y"],
                max_x=bbox["max_x"],
                max_y=bbox["max_y"],
                limit=10,
            )
            products = result.value or []
            for prod in products:
                prod_id = prod.get("Id")
                name = prod.get("Name", "Sentinel-2 Product")
                date_str = prod.get("ContentDate", {}).get("Start")

                if not prod_id:
                    continue

                if date_str:
                    try:
                        # OData ISO timestamp format e.g. "2026-07-24T10:15:00.000Z"
                        event_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    except ValueError:
                        event_date = now
                else:
                    event_date = now

                if event_date < start_dt:
                    continue

                # Centroid of bounding box for spatial point
                lat = (bbox["min_y"] + bbox["max_y"]) / 2.0
                lon = (bbox["min_x"] + bbox["max_x"]) / 2.0
                region = str(bbox["name"])

                # Preserve source attribution metadata in details (Refinement 3)
                source_url = f"https://catalogue.dataspace.copernicus.eu/odata/v1/Products({prod_id})"
                details = (
                    f"Copernicus Sentinel-2 Satellite Product '{name}' | "
                    f"Provider: EU Copernicus Data Space | Original ID: {prod_id} | "
                    f"Source URL: {source_url}"
                )

                records.append(
                    HazardEventRecord(
                        source="copernicus",
                        external_id=f"copernicus_{prod_id}",
                        event_type="wildfire_satellite",
                        region_label=region,
                        point=(lat, lon),
                        event_date=event_date,
                        details=details,
                    )
                )
        except Exception as exc:
            _log.warning(
                "ingestion.source.copernicus.region_failed",
                region=bbox["name"],
                error=str(exc),
            )

    _log.info("ingestion.source.copernicus.completed", records_fetched=len(records))
    return records
