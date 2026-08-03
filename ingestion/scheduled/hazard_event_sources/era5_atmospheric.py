"""Historical hazard event source adapter for ERA5 atmospheric reanalysis baselines."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from ingestion.scheduled.schemas import HazardEventRecord
from logging_config import get_logger
from tools.era5.client import ERA5Client

_log = get_logger(__name__)

# Key atmospheric baseline monitoring locations
MONITORING_LOCATIONS: dict[str, dict[str, Any]] = {
    "Tokyo": {"lat": 35.6762, "lon": 139.6503},
    "London": {"lat": 51.5074, "lon": -0.1278},
    "Paris": {"lat": 48.8566, "lon": 2.3522},
    "California": {"lat": 36.7783, "lon": -119.4179},
}


async def fetch_recent_era5_events(
    since: datetime | None = None,
) -> list[HazardEventRecord]:
    """Fetch recent ERA5 atmospheric reanalysis baseline records.

    Maps ERA5 daily metrics to HazardEventRecord with full source attribution in details.
    """
    now = datetime.now(UTC)
    start_dt = since or (now - timedelta(days=7))

    _log.info("ingestion.source.era5.fetching", since=start_dt.isoformat())

    client = ERA5Client()
    records: list[HazardEventRecord] = []

    start_date = start_dt.date()
    end_date = now.date()

    for city_name, meta in MONITORING_LOCATIONS.items():
        try:
            result = await client.get_atmospheric_baseline(
                lat=meta["lat"],
                lon=meta["lon"],
                start_date=start_date,
                end_date=end_date,
            )
            data = result.value or {}
            daily = data.get("daily", {})
            time_list = daily.get("time", [])
            temp_list = daily.get("temperature_2m_mean", [])
            wind_list = daily.get("wind_speed_10m_max", [])
            precip_list = daily.get("precipitation_sum", [])

            for i, time_str in enumerate(time_list):
                try:
                    event_date = datetime.strptime(str(time_str), "%Y-%m-%d").replace(tzinfo=UTC)
                except ValueError:
                    event_date = now

                if event_date < start_dt:
                    continue

                temp = temp_list[i] if i < len(temp_list) else "N/A"
                wind = wind_list[i] if i < len(wind_list) else "N/A"
                precip = precip_list[i] if i < len(precip_list) else "N/A"

                ext_id = f"era5_{city_name.lower()}_{time_str}"
                source_url = "https://archive-api.open-meteo.com/v1/archive"
                details = (
                    f"ERA5 Atmospheric Reanalysis Baseline in {city_name} on {time_str}: "
                    f"Mean Temp: {temp}°C, Max Wind: {wind} km/h, Precip: {precip} mm | "
                    f"Provider: ECMWF ERA5 | Original ID: {ext_id} | Source URL: {source_url}"
                )

                records.append(
                    HazardEventRecord(
                        source="era5",
                        external_id=ext_id,
                        event_type="atmospheric_anomaly",
                        region_label=city_name,
                        point=(meta["lat"], meta["lon"]),
                        event_date=event_date,
                        details=details,
                    )
                )
        except Exception as exc:
            _log.warning(
                "ingestion.source.era5.location_failed",
                city=city_name,
                error=str(exc),
            )

    _log.info("ingestion.source.era5.completed", records_fetched=len(records))
    return records
