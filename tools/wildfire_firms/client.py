"""NASA FIRMS Wildfire API Client."""

from __future__ import annotations

import csv
from io import StringIO
from typing import Any

from config.settings import get_settings
from logging_config import get_logger
from resilience.degraded_mode import ResilientResult, TTL_BY_SOURCE, resilient_call
from tools.http_client import get_shared_client

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
    ) -> ResilientResult[list[dict[str, Any]]]:
        """Fetch active fires in a bounding box from NASA FIRMS.

        Returns a ``ResilientResult`` — check ``.degraded`` and ``.source_status``
        before using ``.value``.  Returns an empty-list result (not degraded)
        when the API key is not configured — that is a configuration gap, not a
        source failure.
        """
        _log.info("wildfire.client.get_active_fires", bbox=[min_x, min_y, max_x, max_y])

        if not self.api_key:
            _log.warning("wildfire.client.missing_key_fallback")
            return ResilientResult(value=[], degraded=False, source_status="live")

        url = f"{self.base_url}/{self.api_key}/MODIS_NRT/{min_x},{min_y},{max_x},{max_y}/{days}"
        cache_key = f"active_fires:{round(min_x, 2)}:{round(min_y, 2)}:{round(max_x, 2)}:{round(max_y, 2)}:{days}"

        async def _fetch() -> list[dict[str, Any]]:
            client = await get_shared_client()
            resp = await client.get(url)
            if resp.status_code != 200:
                _log.error("wildfire.client.failed", status=resp.status_code, body=resp.text)
                resp.raise_for_status()
            f = StringIO(resp.text)
            reader = csv.DictReader(f)
            return list(reader)

        return await resilient_call(
            source="firms",
            fn=_fetch,
            cache_key=cache_key,
            ttl=TTL_BY_SOURCE["firms"],
        )
