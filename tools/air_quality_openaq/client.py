"""OpenAQ REST API Client for retrieving air quality measurements."""

from __future__ import annotations

from typing import Any

import httpx

from logging_config import get_logger

_log = get_logger(__name__)


class OpenAQClient:
    """Async client to interact with OpenAQ Air Quality API."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key
        self.base_url = "https://api.openaq.org/v2"

    async def get_latest_measurements(self, city: str) -> list[dict[str, Any]]:
        """Fetch latest air quality measurements for a city."""
        _log.info("openaq.client.fetch_latest", city=city)
        headers = {}
        if self.api_key:
            headers["X-API-Key"] = self.api_key

        url = f"{self.base_url}/latest"
        params: dict[str, str | int] = {"city": city, "limit": 10}

        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, headers=headers, timeout=10.0)
            if response.status_code != 200:
                _log.error(
                    "openaq.client.fetch_failed",
                    city=city,
                    status=response.status_code,
                    body=response.text,
                )
                response.raise_for_status()

            data = response.json()
            return data.get("results", [])
