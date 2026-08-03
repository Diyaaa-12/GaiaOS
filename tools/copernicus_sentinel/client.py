"""Copernicus Sentinel API Client for querying satellite metadata and hazard anomalies."""

from __future__ import annotations

from typing import Any

from config.settings import get_settings
from logging_config import get_logger
from resilience.degraded_mode import TTL_BY_SOURCE, ResilientResult, resilient_call
from tools.http_client import get_shared_client

_log = get_logger(__name__)


class CopernicusSentinelClient:
    """Async client to query Copernicus Data Space OData API for satellite product metadata."""

    def __init__(self, base_url: str | None = None) -> None:
        settings = get_settings()
        self.base_url = base_url or settings.copernicus_api_url

    async def get_wildfire_products(
        self,
        min_x: float,
        min_y: float,
        max_x: float,
        max_y: float,
        limit: int = 10,
    ) -> ResilientResult[list[dict[str, Any]]]:
        """Fetch Sentinel-2 satellite product metadata covering bounding box.

        Returns a ``ResilientResult[list[dict]]``. Check ``.degraded`` and
        ``.source_status`` before consuming ``.value``.
        """
        _log.info("copernicus.client.get_wildfire_products", bbox=[min_x, min_y, max_x, max_y])

        # Filter query for Sentinel-2 product metadata in OData format
        filter_str = (
            f"Collection/Name eq 'SENTINEL-2' and "
            f"OData.CSC.Intersects(area=geography'SRID=4326;POLYGON(("
            f"{min_x} {min_y}, {max_x} {min_y}, {max_x} {max_y}, "
            f"{min_x} {max_y}, {min_x} {min_y}))')"
        )
        params: dict[str, str | int] = {
            "$filter": filter_str,
            "$top": limit,
            "$orderby": "ContentDate/Start desc",
        }

        cache_key = (
            f"products:{round(min_x, 2)}:{round(min_y, 2)}:"
            f"{round(max_x, 2)}:{round(max_y, 2)}:{limit}"
        )

        async def _fetch() -> list[dict[str, Any]]:
            client = await get_shared_client()
            url = f"{self.base_url}/Products"
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                _log.error("copernicus.client.failed", status=resp.status_code, body=resp.text)
                resp.raise_for_status()
            data = resp.json()
            return data.get("value", [])  # type: ignore[no-any-return]

        return await resilient_call(
            source="copernicus",
            fn=_fetch,
            cache_key=cache_key,
            ttl=TTL_BY_SOURCE["copernicus"],
        )
