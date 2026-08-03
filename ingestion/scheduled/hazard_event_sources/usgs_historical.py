"""Historical hazard event source adapter for USGS earthquakes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ingestion.scheduled.schemas import HazardEventRecord
from logging_config import get_logger
from tools.seismic_usgs.client import USGSSeismicClient

_log = get_logger(__name__)


async def fetch_recent_usgs_events(
    since: datetime | None = None,
    min_magnitude: float = 2.5,
) -> list[HazardEventRecord]:
    """Fetch recent USGS earthquakes since the provided cursor timestamp.

    If `since` is None, defaults to fetching earthquakes from the past 7 days.
    """
    now = datetime.now(UTC)
    start_dt = since or (now - timedelta(days=7))

    _log.info(
        "ingestion.source.usgs.fetching",
        since=start_dt.isoformat(),
        min_magnitude=min_magnitude,
    )

    client = USGSSeismicClient()
    res = await client.get_recent_earthquakes(
        starttime=start_dt,
        endtime=now,
        min_magnitude=min_magnitude,
    )
    features = res.value or []

    records: list[HazardEventRecord] = []
    for feat in features:
        feat_id = feat.get("id")
        props = feat.get("properties", {})
        geom = feat.get("geometry", {})
        coords = geom.get("coordinates", [])

        if not feat_id or not coords or len(coords) < 2:
            continue

        lon, lat = float(coords[0]), float(coords[1])
        epoch_ms = props.get("time")
        if epoch_ms is None:
            continue

        event_date = datetime.fromtimestamp(epoch_ms / 1000.0, UTC)
        place = props.get("place") or "Unknown location"
        mag = props.get("mag")
        if mag is not None:
            details = f"Magnitude {mag} earthquake - {place}"
        else:
            details = f"Earthquake - {place}"

        records.append(
            HazardEventRecord(
                source="usgs",
                external_id=str(feat_id),
                event_type="earthquake",
                region_label=place,
                point=(lat, lon),
                event_date=event_date,
                details=details,
            )
        )

    _log.info("ingestion.source.usgs.completed", records_fetched=len(records))
    return records
