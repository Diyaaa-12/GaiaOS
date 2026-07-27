"""NOAA CO-OPS API Client for retrieving oceanographic measurements."""

from __future__ import annotations

from typing import Any

from config.settings import get_settings
from logging_config import get_logger
from tools.http_client import get_shared_client

_log = get_logger(__name__)


class NOAAOceanClient:
    """Async client to query NOAA CO-OPS API."""

    def __init__(self, base_url: str | None = None) -> None:
        settings = get_settings()
        self.base_url = base_url or settings.noaa_api_url

    async def get_water_temperature(
        self,
        station_id: str,
        date: str = "latest",
        range_hours: int | None = None,
    ) -> dict[str, Any]:
        """Fetch water temperature at a given NOAA station."""
        _log.info("ocean.client.get_water_temperature", station_id=station_id, date=date)
        params: dict[str, str | int] = {
            "station": station_id,
            "product": "water_temperature",
            "date": date,
            "units": "metric",
            "time_zone": "gmt",
            "application": "gaiaos",
            "format": "json",
        }
        if range_hours is not None:
            params["range"] = range_hours

        client = await get_shared_client()
        resp = await client.get(self.base_url, params=params)
        if resp.status_code != 200:
            _log.error("ocean.client.failed", status=resp.status_code, body=resp.text)
            resp.raise_for_status()

        data = resp.json()
        if "error" in data:
            _log.warning("ocean.client.api_error", error=data["error"])
            return {}
        return data
