"""USGS Seismic API Client for retrieving earthquake details."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from config.settings import get_settings
from logging_config import get_logger
from resilience.degraded_mode import TTL_BY_SOURCE, ResilientResult, resilient_call
from tools.http_client import get_shared_client

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
        starttime: datetime | None = None,
        endtime: datetime | None = None,
    ) -> ResilientResult[list[dict[str, Any]]]:
        """Fetch recent earthquakes from USGS matching criteria.

        Returns a ``ResilientResult`` — check ``.degraded`` and ``.source_status``
        before using ``.value``.  ``.value`` is ``None`` when the source is
        unavailable and no cached response exists.
        """
        _log.info(
            "seismic.client.get_recent_earthquakes",
            lat=lat,
            lon=lon,
            radius_km=radius_km,
            min_magnitude=min_magnitude,
            days=days,
            starttime=starttime,
            endtime=endtime,
        )

        end_dt = endtime or datetime.now(UTC)
        start_dt = starttime or (end_dt - timedelta(days=days))

        params: dict[str, str | int | float] = {
            "format": "geojson",
            "starttime": start_dt.isoformat(),
            "endtime": end_dt.isoformat(),
            "minmagnitude": min_magnitude,
        }

        if lat is not None and lon is not None and radius_km is not None:
            params["latitude"] = lat
            params["longitude"] = lon
            params["maxradiuskm"] = radius_km

        # Cache key encodes the query dimensions
        cache_key = (
            f"earthquakes:{round(lat or 0, 2)}:{round(lon or 0, 2)}"
            f":{radius_km}:{min_magnitude}:{days}"
        )

        async def _fetch() -> list[dict[str, Any]]:
            client = await get_shared_client()
            resp = await client.get(self.base_url, params=params)
            if resp.status_code != 200:
                _log.error("seismic.client.failed", status=resp.status_code, body=resp.text)
                resp.raise_for_status()
            data = resp.json()
            return data.get("features", [])

        return await resilient_call(
            source="usgs",
            fn=_fetch,
            cache_key=cache_key,
            ttl=TTL_BY_SOURCE["usgs"],
        )
