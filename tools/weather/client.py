"""Open-Meteo Weather API Client for atmospheric observations."""

from __future__ import annotations

from typing import Any

from config.settings import get_settings
from logging_config import get_logger
from tools.http_client import get_shared_client

_log = get_logger(__name__)


class WeatherClient:
    """Async client to fetch weather metrics from Open-Meteo API."""

    def __init__(self, base_url: str | None = None) -> None:
        settings = get_settings()
        self.base_url = base_url or settings.open_meteo_weather_url

    async def get_current_weather(self, lat: float, lon: float) -> dict[str, Any]:
        """Fetch current weather metrics (temperature, wind speed, relative humidity)."""
        _log.info("weather.client.get_current_weather", lat=lat, lon=lon)
        params: dict[str, str | float] = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,wind_speed_10m,relative_humidity_2m",
        }

        client = await get_shared_client()
        resp = await client.get(self.base_url, params=params)
        if resp.status_code != 200:
            _log.error("weather.client.failed", status=resp.status_code, body=resp.text)
            resp.raise_for_status()

        return resp.json()
