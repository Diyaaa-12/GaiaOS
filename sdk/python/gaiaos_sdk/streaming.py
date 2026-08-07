"""Server-Sent Events (SSE) streaming wrapper for GaiaOS investigation traces."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator, Generator
from typing import Any

import httpx
from httpx_sse import aconnect_sse, connect_sse
from pydantic import BaseModel, Field


class StreamEvent(BaseModel):
    """Container for parsed SSE events emitted by GaiaOS during investigation execution."""

    event_type: str = Field(alias="event", default="message")
    data: dict[str, Any] = Field(default_factory=dict)
    id: str | None = None
    retry: int | None = None


def _parse_sse_data(raw_data: str) -> dict[str, Any]:
    """Parse raw JSON string payload from SSE event data safely."""
    if not raw_data:
        return {}
    try:
        parsed = json.loads(raw_data)
        return parsed if isinstance(parsed, dict) else {"content": parsed}
    except Exception:
        return {"raw": raw_data}


def stream_investigation_events(
    client: httpx.Client,
    url: str,
    headers: dict[str, str] | None = None,
) -> Generator[StreamEvent, None, None]:
    """Synchronous generator yielding StreamEvent items from an SSE endpoint."""
    with connect_sse(client, "GET", url, headers=headers) as event_source:
        for sse in event_source.iter_sse():
            event_data = _parse_sse_data(sse.data)
            yield StreamEvent(
                event=sse.event or "message",
                data=event_data,
                id=sse.id,
                retry=sse.retry,
            )


async def astream_investigation_events(
    client: httpx.AsyncClient,
    url: str,
    headers: dict[str, str] | None = None,
) -> AsyncGenerator[StreamEvent, None]:
    """Asynchronous generator yielding StreamEvent items from an SSE endpoint."""
    async with aconnect_sse(client, "GET", url, headers=headers) as event_source:
        async for sse in event_source.aiter_sse():
            event_data = _parse_sse_data(sse.data)
            yield StreamEvent(
                event=sse.event or "message",
                data=event_data,
                id=sse.id,
                retry=sse.retry,
            )
