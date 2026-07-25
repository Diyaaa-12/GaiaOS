"""Historical hazard event source adapter for NOAA oceanographic observations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from ingestion.scheduled.schemas import HazardEventRecord
from logging_config import get_logger
from tools.geocoding import LOCAL_GEOCODE_DB
from tools.ocean_noaa.client import NOAAOceanClient

_log = get_logger(__name__)


async def fetch_recent_noaa_events(
    since: datetime | None = None,
) -> list[HazardEventRecord]:
    """Fetch recent NOAA oceanographic observations for key monitoring stations.

    Maps NOAA water temperature measurements to HazardEventRecord.
    """
    now = datetime.now(UTC)
    start_dt = since or (now - timedelta(days=7))

    _log.info("ingestion.source.noaa.fetching", since=start_dt.isoformat())

    client = NOAAOceanClient()
    records: list[HazardEventRecord] = []

    # Map city station IDs to coordinates from LOCAL_GEOCODE_DB
    stations_to_process: dict[str, dict[str, Any]] = {}
    for city, geo_data in LOCAL_GEOCODE_DB.items():
        st_id = geo_data.get("station_id")
        if st_id and st_id not in stations_to_process:
            lat_raw = geo_data.get("lat", 0.0)
            lon_raw = geo_data.get("lon", 0.0)
            stations_to_process[str(st_id)] = {
                "city": city.capitalize(),
                "lat": float(str(lat_raw)),
                "lon": float(str(lon_raw)),
            }

    for station_id, meta in stations_to_process.items():
        try:
            temp_data = await client.get_water_temperature(station_id=station_id, date="latest")
            obs_list = temp_data.get("data", [])
            if isinstance(obs_list, list):
                for obs in obs_list:
                    if not isinstance(obs, dict):
                        continue
                    t_str = obs.get("t")  # Timestamp "2026-07-24 18:00"
                    v_str = obs.get("v")  # Temperature value
                    if not t_str or not v_str:
                        continue

                    try:
                        dt_val = datetime.strptime(str(t_str), "%Y-%m-%d %H:%M").replace(tzinfo=UTC)
                    except ValueError:
                        dt_val = now

                    if dt_val < start_dt:
                        continue

                    city_label = str(meta["city"])
                    lat_val = float(meta["lat"])
                    lon_val = float(meta["lon"])
                    ext_id = f"noaa_{station_id}_{str(t_str).replace(' ', 'T')}"
                    details = (
                        f"NOAA station {station_id} "
                        f"({city_label}) water temperature: {v_str}°C"
                    )

                    records.append(
                        HazardEventRecord(
                            source="noaa",
                            external_id=ext_id,
                            event_type="marine heatwave",
                            region_label=city_label,
                            point=(lat_val, lon_val),
                            event_date=dt_val,
                            details=details,
                        )
                    )
        except Exception as e:
            _log.warning(
                "ingestion.source.noaa.station_failed",
                station_id=station_id,
                error=str(e),
            )

    _log.info("ingestion.source.noaa.completed", records_fetched=len(records))
    return records
