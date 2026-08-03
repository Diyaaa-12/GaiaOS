"""OpenAQ REST API Client for retrieving air quality measurements."""

from __future__ import annotations

from typing import Any

from logging_config import get_logger
from resilience.degraded_mode import ResilientResult, TTL_BY_SOURCE, resilient_call
from tools.http_client import get_shared_client

_log = get_logger(__name__)


class OpenAQClient:
    """Async client to interact with OpenAQ Air Quality API."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key
        self.base_url = "https://api.openaq.org/v2"

    async def get_latest_measurements(
        self, city: str
    ) -> ResilientResult[list[dict[str, Any]]]:
        """Fetch latest air quality measurements for a city.

        Returns a ``ResilientResult`` — check ``.degraded`` and ``.source_status``
        before using ``.value``.  ``.value`` is ``None`` when the source is
        unavailable and no cached response exists.
        """
        _log.info("openaq.client.fetch_latest", city=city)

        headers: dict[str, str] = {}
        if self.api_key:
            headers["X-API-Key"] = self.api_key

        url = f"{self.base_url}/latest"
        params: dict[str, str | int] = {"city": city, "limit": 10}
        cache_key = f"latest_measurements:{city.lower()}"

        async def _fetch() -> list[dict[str, Any]]:
            client = await get_shared_client()
            response = await client.get(url, params=params, headers=headers)
            if response.status_code != 200:
                _log.error(
                    "openaq.client.fetch_failed",
                    city=city,
                    status=response.status_code,
                    body=response.text,
                )
                response.raise_for_status()
            data = response.json()
            return data.get("results", [])  # type: ignore[no-any-return]

        return await resilient_call(
            source="openaq",
            fn=_fetch,
            cache_key=cache_key,
            ttl=TTL_BY_SOURCE["openaq"],
        )
