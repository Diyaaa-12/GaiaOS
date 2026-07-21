"""Async Redis client and lifecycle management.

Follows the lazy-initialisation and lifespan-linked lifecycle pattern used by
the PostgreSQL database connection layer in ``db.session``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING
from uuid import UUID

from redis.asyncio import Redis, from_url

from logging_config import get_logger
from orchestrator.schemas.events import InvestigationEvent

if TYPE_CHECKING:
    from config.settings import Settings

_log = get_logger(__name__)

# Module-level singleton instance, initialised by init_redis() and disposed by dispose_redis()
redis_client: Redis | None = None


async def init_redis(settings: Settings) -> None:
    """Initialise the async Redis connection pool and verify connectivity.

    Must be called once during application startup (lifespan hook).
    Idempotent: subsequent calls replace the existing client reference.

    Raises ``RuntimeError`` if ``REDIS_URL`` is not configured or if the
    Redis server is unreachable.
    """
    global redis_client

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
    _log.info("redis.client.ready")


async def dispose_redis() -> None:
    """Close the Redis client and release all connection pool resources.

    Must be called during application shutdown (lifespan hook).
    Safe to call even if ``init_redis()`` was never called.
    """
    global redis_client
    if redis_client is not None:
        await redis_client.aclose()
        redis_client = None
        _log.info("redis.client.disposed")


async def get_redis() -> Redis:
    """Return the active Redis client instance.

    Intended for use as a dependency provider.
    Raises ``RuntimeError`` if the client has not been initialised.
    """
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
