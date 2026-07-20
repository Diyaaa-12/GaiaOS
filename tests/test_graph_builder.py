"""Tests for LangGraph StateGraph compiling and RedisCheckpointer verification."""

from __future__ import annotations

import os
import uuid

import pytest
from redis.asyncio import Redis

from orchestrator.graph.builder import build_graph
from orchestrator.graph.checkpointer import RedisCheckpointSaver


class TestGraphBuilder:
    """Verifies graph building and state checkpointing lifecycle."""

    async def test_graph_compiles_successfully(self) -> None:
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        client = Redis.from_url(redis_url)

        checkpointer = RedisCheckpointSaver(client)
        graph = build_graph(checkpointer)

        assert graph is not None
        assert "supervisor" in graph.nodes
        assert "air_quality" in graph.nodes
        assert "synthesis" in graph.nodes
        await client.aclose()

    async def test_redis_checkpointer_lifecycle(self) -> None:
        redis_url = os.environ.get("REDIS_URL")
        if not redis_url:
            pytest.skip("REDIS_URL environment variable is not set — skipping integration test.")
        client = Redis.from_url(redis_url)

        checkpointer = RedisCheckpointSaver(client)
        thread_id = str(uuid.uuid4())

        config = {"configurable": {"thread_id": thread_id}}

        # 1. Fetch missing checkpoint
        tup = await checkpointer.aget_tuple(config)
        assert tup is None

        # 2. Put a checkpoint
        checkpoint = {
            "v": 1,
            "id": str(uuid.uuid4()),
            "ts": "2026-07-20T00:00:00Z",
            "channel_values": {"query": "hello"},
            "channel_versions": {},
            "versions_seen": {},
            "pending_sends": [],
        }
        metadata = {"step": 0, "source": "input"}

        new_config = await checkpointer.aput(config, checkpoint, metadata, {})
        assert new_config["configurable"]["thread_id"] == thread_id

        # 3. Retrieve checkpoint
        tup = await checkpointer.aget_tuple(config)
        assert tup is not None
        assert tup.checkpoint["id"] == checkpoint["id"]
        assert tup.checkpoint["channel_values"]["query"] == "hello"

        # 4. List checkpoints
        tuples = []
        async for t in checkpointer.alist(config):
            tuples.append(t)
        assert len(tuples) == 1
        assert tuples[0].checkpoint["id"] == checkpoint["id"]

        # Clean up
        await client.delete(f"gaiaos:checkpoint:{thread_id}:latest")
        await client.delete(f"gaiaos:checkpoint:{thread_id}:checkpoint:{checkpoint['id']}")
        await client.aclose()
