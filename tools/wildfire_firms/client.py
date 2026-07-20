"""NASA FIRMS Wildfire API Client."""

from __future__ import annotations

import csv
from io import StringIO
from typing import Any

import httpx

from config.settings import get_settings
from logging_config import get_logger

_log = get_logger(__name__)


class FIRMSWildfireClient:
    """Async client to fetch active fires from NASA FIRMS."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.firms_api_key
        self.base_url = base_url or settings.firms_api_url

    async def get_active_fires(
        self,
        min_x: float,
        min_y: float,
        max_x: float,
        max_y: float,
        days: int = 1,
    ) -> list[dict[str, Any]]:
        """Fetch active fires in a bounding box from NASA FIRMS."""
        _log.info("wildfire.client.get_active_fires", bbox=[min_x, min_y, max_x, max_y])
        if not self.api_key:
            _log.warning("wildfire.client.missing_key_fallback")
            return []

        # URL format: {base_url}/{api_key}/MODIS_NRT/{min_x},{min_y},{max_x},{max_y}/{days}
        url = f"{self.base_url}/{self.api_key}/MODIS_NRT/{min_x},{min_y},{max_x},{max_y}/{days}"

        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=10.0)
            if resp.status_code != 200:
                _log.error("wildfire.client.failed", status=resp.status_code, body=resp.text)
                resp.raise_for_status()

            csv_data = resp.text
            f = StringIO(csv_data)
            reader = csv.DictReader(f)
            return list(reader)
