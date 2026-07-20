"""NOAA CO-OPS API Client for retrieving oceanographic measurements."""

from __future__ import annotations

from typing import Any

import httpx

from config.settings import get_settings
from logging_config import get_logger

_log = get_logger(__name__)


class NOAAOceanClient:
    """Async client to query NOAA CO-OPS API."""

    def __init__(self, base_url: str | None = None) -> None:
        settings = get_settings()
        self.base_url = base_url or settings.noaa_api_url

    async def get_water_temperature(self, station_id: str) -> dict[str, Any]:
        """Fetch latest water temperature at a given NOAA station."""
        _log.info("ocean.client.get_water_temperature", station_id=station_id)
        params = {
            "station": station_id,
            "product": "water_temperature",
            "date": "latest",
            "units": "metric",
            "time_zone": "lst_ldt",
            "application": "gaiaos",
            "format": "json",
        }
        async with httpx.AsyncClient() as client:
            resp = await client.get(self.base_url, params=params, timeout=10.0)
            if resp.status_code != 200:
                _log.error("ocean.client.failed", status=resp.status_code, body=resp.text)
                resp.raise_for_status()

            data = resp.json()
            if "error" in data:
                _log.warning("ocean.client.api_error", error=data["error"])
                return {}
            return data
