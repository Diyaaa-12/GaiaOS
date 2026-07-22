"""Open-Meteo Weather API Client for atmospheric observations."""

from __future__ import annotations

from typing import Any

import httpx

from config.settings import get_settings
from logging_config import get_logger

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

        async with httpx.AsyncClient() as client:
            resp = await client.get(self.base_url, params=params, timeout=10.0)
            if resp.status_code != 200:
                _log.error("weather.client.failed", status=resp.status_code, body=resp.text)
                resp.raise_for_status()

            return resp.json()
