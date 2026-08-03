"""GDELT DOC 2.0 API Client for socio-political hazard context ingestion."""

from __future__ import annotations

from typing import Any

from config.settings import get_settings
from logging_config import get_logger
from resilience.degraded_mode import ResilientResult, TTL_BY_SOURCE, resilient_call
from tools.http_client import get_shared_client

_log = get_logger(__name__)


class GDELTClient:
    """Async client to fetch socio-political and environmental hazard news events from GDELT DOC 2.0 API."""

    def __init__(self, base_url: str | None = None) -> None:
        settings = get_settings()
        self.base_url = base_url or settings.gdelt_api_url
        self.max_records = settings.gdelt_max_records_per_run

    async def get_hazard_articles(
        self,
        query: str = "hazard OR disaster OR evacuation OR unrest",
        max_records: int | None = None,
        start_datetime: str | None = None,
    ) -> ResilientResult[list[dict[str, Any]]]:
        """Fetch news article metadata for environmental/socio-political hazards.

        Returns a ``ResilientResult[list[dict]]``. Check ``.degraded`` and
        ``.source_status`` before consuming ``.value``.
        """
        limit = max_records or self.max_records
        _log.info("gdelt.client.get_hazard_articles", query=query, max_records=limit)

        params: dict[str, str | int] = {
            "query": query,
            "mode": "artlist",
            "maxrecords": limit,
            "format": "json",
        }
        if start_datetime:
            params["startdatetime"] = start_datetime

        cache_key = f"articles:{query}:{limit}:{start_datetime or 'latest'}"

        async def _fetch() -> list[dict[str, Any]]:
            client = await get_shared_client()
            resp = await client.get(self.base_url, params=params)
            if resp.status_code != 200:
                _log.error("gdelt.client.failed", status=resp.status_code, body=resp.text)
                resp.raise_for_status()
            try:
                data = resp.json()
                return data.get("articles", [])  # type: ignore[no-any-return]
            except Exception as exc:
                _log.warning("gdelt.client.parse_error", error=str(exc))
                return []

        return await resilient_call(
            source="gdelt",
            fn=_fetch,
            cache_key=cache_key,
            ttl=TTL_BY_SOURCE["gdelt"],
        )
