"""Async Redis client and lifecycle management.

Follows the lazy-initialisation and lifespan-linked lifecycle pattern used by
the PostgreSQL database connection layer in ``db.session``.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING
from uuid import UUID

from redis.asyncio import Redis, from_url

from logging_config import get_logger
from orchestrator.schemas.events import InvestigationEvent

if TYPE_CHECKING:
    from config.settings import Settings

_log = get_logger(__name__)

# Module-level singleton instance and its owning event loop
redis_client: Redis | None = None
_redis_loop: asyncio.AbstractEventLoop | None = None


async def init_redis(settings: Settings) -> None:
    """Initialise the async Redis connection pool and verify connectivity.

    Must be called once during application startup (lifespan hook).
    Idempotent: subsequent calls replace the existing client reference.

    Raises ``RuntimeError`` if ``REDIS_URL`` is not configured or if the
    Redis server is unreachable.
    """
    global redis_client, _redis_loop

    if settings.redis_url is None:
        raise RuntimeError(
            "REDIS_URL is not set.  The Redis connection layer cannot be initialised without it."
        )

    _log.info("redis.client.init", url=settings.redis_url)

    # Create client with connection pool
    client = from_url(
        settings.redis_url,
        decode_responses=True,
        # Default socket configuration
        socket_connect_timeout=5.0,
        socket_timeout=5.0,
    )

    # Verify connectivity (fail-fast startup check)
    try:
        await client.ping()
    except Exception as exc:
        await client.aclose()
        _log.error("redis.client.connect_failed", url=settings.redis_url, error=str(exc))
        raise RuntimeError(f"Failed to connect to Redis at {settings.redis_url}: {exc}") from exc

    redis_client = client
    _redis_loop = asyncio.get_running_loop()
    _log.info("redis.client.ready")


async def dispose_redis() -> None:
    """Close the Redis client and release all connection pool resources.

    Must be called during application shutdown (lifespan hook).
    Safe to call even if ``init_redis()`` was never called.
    """
    global redis_client, _redis_loop
    if redis_client is not None:
        try:
            await redis_client.aclose()
        except Exception:
            pass
        redis_client = None
        _redis_loop = None
        _log.info("redis.client.disposed")


async def get_redis() -> Redis:
    """Return the active Redis client instance bound to the current running event loop.

    Intended for use as a dependency provider.
    Re-initialises the client if the running event loop changes (e.g. between RQ jobs).
    Raises ``RuntimeError`` if the client has not been initialised.
    """
    global redis_client, _redis_loop

    current_loop = asyncio.get_running_loop()
    if redis_client is not None and _redis_loop is not current_loop:
        _log.info("redis.client.loop_mismatch_recreating")
        await dispose_redis()
        from config.settings import get_settings

        settings = get_settings()
        if settings.redis_url:
            await init_redis(settings)

    if redis_client is None:
        raise RuntimeError(
            "Redis client is not initialised.  "
            "Ensure init_redis() is called during application startup."
        )
    return redis_client


def parse_event(json_str: str) -> InvestigationEvent:
    """Parse JSON string into a typed InvestigationEvent."""
    import json

    from orchestrator.schemas.events import (
        AgentCompletedEvent,
        AgentStartedEvent,
        CriticFlagEvent,
        DoneEvent,
        PlanningEvent,
        SynthesizingEvent,
    )

    data = json.loads(json_str)
    event_type = data.get("event")
    if event_type == "planning":
        return PlanningEvent(**data)
    elif event_type == "agent_started":
        return AgentStartedEvent(**data)
    elif event_type == "agent_completed":
        return AgentCompletedEvent(**data)
    elif event_type == "synthesizing":
        return SynthesizingEvent(**data)
    elif event_type == "critic_flag":
        return CriticFlagEvent(**data)
    elif event_type == "done":
        return DoneEvent(**data)
    else:
        raise ValueError(f"Unknown event type: {event_type}")


async def publish_event(investigation_id: UUID, event: InvestigationEvent) -> None:
    """Publish an InvestigationEvent to the Redis pub/sub channel."""
    from cache.keys import RedisKeyBuilder

    client = await get_redis()
    channel = RedisKeyBuilder.event_channel_key(str(investigation_id))
    serialized = event.model_dump_json()
    await client.publish(channel, serialized)


async def subscribe(investigation_id: UUID) -> AsyncIterator[InvestigationEvent]:
    """Subscribe to the Redis channel for the given investigation ID.

    Yields:
        InvestigationEvent: The deserialized event streamed from the channel.
    """
    from cache.keys import RedisKeyBuilder

    client = await get_redis()
    channel = RedisKeyBuilder.event_channel_key(str(investigation_id))
    pubsub = client.pubsub()
    await pubsub.subscribe(channel)
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                data_str = message["data"]
                yield parse_event(data_str)
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()
