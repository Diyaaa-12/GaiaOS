"""Open-Meteo Weather API Client for atmospheric observations."""

from __future__ import annotations

from typing import Any

from config.settings import get_settings
from logging_config import get_logger
from resilience.degraded_mode import TTL_BY_SOURCE, ResilientResult, resilient_call
from tools.http_client import get_shared_client

_log = get_logger(__name__)


class WeatherClient:
    """Async client to fetch weather metrics from Open-Meteo API."""

    def __init__(self, base_url: str | None = None) -> None:
        settings = get_settings()
        self.base_url = base_url or settings.open_meteo_weather_url

    async def get_current_weather(
        self, lat: float, lon: float
    ) -> ResilientResult[dict[str, Any]]:
        """Fetch current weather metrics (temperature, wind speed, relative humidity).

        Returns a ``ResilientResult`` — check ``.degraded`` and ``.source_status``
        before using ``.value``.  ``.value`` is ``None`` when the source is
        unavailable and no cached response exists.
        """
        _log.info("weather.client.get_current_weather", lat=lat, lon=lon)

        params: dict[str, str | float] = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,wind_speed_10m,relative_humidity_2m",
        }
        cache_key = f"current_weather:{round(lat, 2)}:{round(lon, 2)}"

        async def _fetch() -> dict[str, Any]:
            client = await get_shared_client()
            resp = await client.get(self.base_url, params=params)
            if resp.status_code != 200:
                _log.error("weather.client.failed", status=resp.status_code, body=resp.text)
                resp.raise_for_status()
            return resp.json()  # type: ignore[no-any-return]

        return await resilient_call(
            source="open_meteo",
            fn=_fetch,
            cache_key=cache_key,
            ttl=TTL_BY_SOURCE["open_meteo"],
        )
