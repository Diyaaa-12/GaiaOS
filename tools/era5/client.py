"""ERA5 Client for retrieving historical atmospheric reanalysis baselines."""

from __future__ import annotations

from datetime import date
from typing import Any

from config.settings import get_settings
from logging_config import get_logger
from resilience.degraded_mode import ResilientResult, TTL_BY_SOURCE, resilient_call
from tools.http_client import get_shared_client

_log = get_logger(__name__)


class ERA5Client:
    """Async client to fetch ERA5 atmospheric reanalysis baseline metrics."""

    def __init__(self, base_url: str | None = None) -> None:
        settings = get_settings()
        self.base_url = base_url or settings.era5_api_url

    async def get_atmospheric_baseline(
        self,
        lat: float,
        lon: float,
        start_date: date,
        end_date: date,
    ) -> ResilientResult[dict[str, Any]]:
        """Fetch ERA5 atmospheric baseline metrics for coordinates and date range.

        Returns a ``ResilientResult[dict]``.
        """
        _log.info(
            "era5.client.get_atmospheric_baseline",
            lat=lat,
            lon=lon,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
        )

        params: dict[str, str | float] = {
            "latitude": lat,
            "longitude": lon,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "daily": "temperature_2m_mean,wind_speed_10m_max,precipitation_sum",
        }

        cache_key = f"baseline:{round(lat, 2)}:{round(lon, 2)}:{start_date.isoformat()}:{end_date.isoformat()}"

        async def _fetch() -> dict[str, Any]:
            client = await get_shared_client()
            resp = await client.get(self.base_url, params=params)
            if resp.status_code != 200:
                _log.error("era5.client.failed", status=resp.status_code, body=resp.text)
                resp.raise_for_status()
            return resp.json()  # type: ignore[no-any-return]

        return await resilient_call(
            source="era5",
            fn=_fetch,
            cache_key=cache_key,
            ttl=TTL_BY_SOURCE["era5"],
        )
