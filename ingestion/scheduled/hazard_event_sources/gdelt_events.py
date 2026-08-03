"""Historical hazard event source adapter for GDELT socio-political hazard news events."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

from ingestion.scheduled.schemas import HazardEventRecord
from logging_config import get_logger
from tools.gdelt.client import GDELTClient

_log = get_logger(__name__)


def _parse_gdelt_date(seendate: str | None) -> datetime:
    """Parse GDELT seendate format e.g. '20260724T120000Z' or '20260724120000' to timezone-aware UTC datetime."""
    if not seendate:
        return datetime.now(UTC)
    s = str(seendate).replace("Z", "").replace("T", "")
    try:
        return datetime.strptime(s[:14], "%Y%m%d%H%M%S").replace(tzinfo=UTC)
    except (ValueError, IndexError):
        try:
            return datetime.strptime(s[:8], "%Y%m%d").replace(tzinfo=UTC)
        except ValueError:
            return datetime.now(UTC)


async def fetch_recent_gdelt_events(
    since: datetime | None = None,
) -> list[HazardEventRecord]:
    """Fetch recent GDELT socio-political and environmental hazard news events.

    Maps GDELT DOC 2.0 article entries to HazardEventRecord with full source attribution in details.
    Enforces cursor monotonicity and deduplication.
    """
    now = datetime.now(UTC)
    start_dt = since or (now - timedelta(days=7))

    _log.info("ingestion.source.gdelt.fetching", since=start_dt.isoformat())

    client = GDELTClient()
    start_str = start_dt.strftime("%Y%m%d%H%M%S")

    result = await client.get_hazard_articles(
        query="wildfire OR flood OR earthquake",
        start_datetime=start_str,
    )

    articles = result.value or []
    records: list[HazardEventRecord] = []

    for art in articles:
        url = art.get("url")
        title = art.get("title") or "Socio-Political Hazard Event Report"
        seendate_str = art.get("seendate")
        domain = art.get("domain") or "news"
        language = art.get("language") or "English"

        if not url:
            continue

        event_date = _parse_gdelt_date(seendate_str)

        # Enforce cursor monotonicity: filter out events older than since
        if event_date < start_dt:
            continue

        # Generate deterministic external_id from URL hash
        url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
        ext_id = f"gdelt_{url_hash}"

        # Preserve source attribution metadata in details (Refinement 3)
        details = (
            f"GDELT News Report: '{title}' | "
            f"Provider: GDELT Project ({domain}) | Language: {language} | "
            f"Original ID: {ext_id} | Source URL: {url}"
        )

        # Default spatial coordinates for global news events (0.0, 0.0) with domain/country label
        records.append(
            HazardEventRecord(
                source="gdelt",
                external_id=ext_id,
                event_type="civil_unrest_hazard_adjacent",
                region_label=domain,
                point=(0.0, 0.0),
                event_date=event_date,
                details=details,
            )
        )

    # Sort records chronologically to maintain strict cursor monotonicity
    records.sort(key=lambda r: r.event_date)

    _log.info("ingestion.source.gdelt.completed", records_fetched=len(records))
    return records
