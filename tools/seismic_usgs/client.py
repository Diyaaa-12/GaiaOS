"""USGS Seismic API Client for retrieving earthquake details."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from config.settings import get_settings
from logging_config import get_logger

_log = get_logger(__name__)


class USGSSeismicClient:
    """Async client to query the USGS Earthquake API."""

    def __init__(self, base_url: str | None = None) -> None:
        settings = get_settings()
        self.base_url = base_url or settings.usgs_api_url

    async def get_recent_earthquakes(
        self,
        lat: float | None = None,
        lon: float | None = None,
        radius_km: float | None = None,
        min_magnitude: float = 1.0,
        days: int = 7,
    ) -> list[dict[str, Any]]:
        """Fetch recent earthquakes from USGS matching criteria."""
        _log.info(
            "seismic.client.get_recent_earthquakes",
            lat=lat,
            lon=lon,
            radius_km=radius_km,
            min_magnitude=min_magnitude,
            days=days,
        )

        endtime = datetime.now(UTC)
        starttime = endtime - timedelta(days=days)

        params: dict[str, str | int | float] = {
            "format": "geojson",
            "starttime": starttime.isoformat(),
            "endtime": endtime.isoformat(),
            "minmagnitude": min_magnitude,
        }

        if lat is not None and lon is not None and radius_km is not None:
            params["latitude"] = lat
            params["longitude"] = lon
            params["maxradiuskm"] = radius_km

        async with httpx.AsyncClient() as client:
            resp = await client.get(self.base_url, params=params, timeout=10.0)
            if resp.status_code != 200:
                _log.error("seismic.client.failed", status=resp.status_code, body=resp.text)
                resp.raise_for_status()

            data = resp.json()
            return data.get("features", [])
