"""Unit and integration tests for Redis checkpoint TTL calculation and key expiration."""

from __future__ import annotations

import asyncio
import os
import subprocess
import time
import uuid
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
import redis.asyncio
from langgraph.checkpoint.base import (
    Checkpoint,
    CheckpointMetadata,
    RunnableConfig,
)

from config.settings import Settings, get_settings
from orchestrator.graph.checkpointer import RedisCheckpointSaver


class TestSettingsCheckpointTTL:
    """Test dynamic checkpoint TTL calculation and env overrides in Settings."""

    def test_default_ttl_calculation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify default formula: job_timeout (600) * (retries (2) + 1) * safety (2.0) = 3600s."""
        monkeypatch.delenv("JOB_TIMEOUT_SECONDS", raising=False)
        monkeypatch.delenv("JOB_MAX_RETRIES", raising=False)
        monkeypatch.delenv("CHECKPOINT_TTL_SAFETY_FACTOR", raising=False)
        monkeypatch.delenv("CHECKPOINT_TTL_SECONDS", raising=False)

        settings = Settings(_env_file=None)  # type: ignore[call-arg]
        assert settings.job_timeout_seconds == 600
        assert settings.job_max_retries == 2
        assert settings.checkpoint_ttl_safety_factor == 2.0
        assert settings.checkpoint_ttl_seconds_override is None

        # 600 * (2 + 1) * 2.0 = 3600
        assert settings.checkpoint_ttl_seconds == 3600

    def test_explicit_ttl_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify CHECKPOINT_TTL_SECONDS explicitly overrides calculated default."""
        monkeypatch.setenv("CHECKPOINT_TTL_SECONDS", "1800")

        settings = Settings(_env_file=None)  # type: ignore[call-arg]
        assert settings.checkpoint_ttl_seconds_override == 1800
        assert settings.checkpoint_ttl_seconds == 1800

    def test_custom_job_timeout_and_retries(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify TTL calculation adapts when job timeout or retry parameters change."""
        monkeypatch.delenv("CHECKPOINT_TTL_SECONDS", raising=False)
        monkeypatch.setenv("JOB_TIMEOUT_SECONDS", "300")
        monkeypatch.setenv("JOB_MAX_RETRIES", "1")
        monkeypatch.setenv("CHECKPOINT_TTL_SAFETY_FACTOR", "1.5")

        settings = Settings(_env_file=None)  # type: ignore[call-arg]
        # 300 * (1 + 1) * 1.5 = 900
        assert settings.checkpoint_ttl_seconds == 900


class TestRedisCheckpointerTTL:
    """Test TTL parameter passing in RedisCheckpointSaver."""

    def test_checkpointer_uses_settings_ttl_by_default(self) -> None:
        """RedisCheckpointSaver inherits checkpoint_ttl_seconds from get_settings() by default."""
        mock_redis = MagicMock()
        checkpointer = RedisCheckpointSaver(mock_redis)
        assert checkpointer.ttl_seconds == get_settings().checkpoint_ttl_seconds

    def test_checkpointer_accepts_custom_ttl(self) -> None:
        """RedisCheckpointSaver accepts an explicit ttl_seconds override in constructor."""
        mock_redis = MagicMock()
        checkpointer = RedisCheckpointSaver(mock_redis, ttl_seconds=120)
        assert checkpointer.ttl_seconds == 120

    @pytest.mark.asyncio
    async def test_aput_applies_ttl_to_redis_keys(self) -> None:
        """aput passes ex=ttl_seconds to Redis set for checkpoint and latest keys."""
        mock_redis = MagicMock()
        mock_redis.set = AsyncMock()

        checkpointer = RedisCheckpointSaver(mock_redis, ttl_seconds=3600)

        config = {"configurable": {"thread_id": "test_thread_123"}}
        checkpoint = {"id": "chk_001", "ts": "2026-07-24T10:00:00Z", "v": 1}
        metadata = {"source": "unit_test"}

        res = await checkpointer.aput(config, checkpoint, metadata, new_versions={})  # type: ignore[arg-type]
        assert res["configurable"]["checkpoint_id"] == "chk_001"

        # Verify set calls include ex=3600
        assert mock_redis.set.call_count == 2

        key_call, latest_call = mock_redis.set.call_args_list

        # Checkpoint key set call
        assert key_call[0][0] == "gaiaos:checkpoint:test_thread_123:checkpoint:chk_001"
        assert key_call[1]["ex"] == 3600

        # Latest key set call
        assert latest_call[0][0] == "gaiaos:checkpoint:test_thread_123:latest"
        assert latest_call[0][1] == "chk_001"
        assert latest_call[1]["ex"] == 3600

    @pytest.mark.asyncio
    async def test_aput_writes_applies_ttl_to_redis_key(self) -> None:
        """aput_writes passes ex=ttl_seconds to Redis set for write key."""
        mock_redis = MagicMock()
        mock_redis.set = AsyncMock()

        checkpointer = RedisCheckpointSaver(mock_redis, ttl_seconds=1800)

        config = cast(
            RunnableConfig,
            {
                "configurable": {
                    "thread_id": "test_thread_123",
                    "checkpoint_id": "chk_001",
                }
            },
        )
        writes = [("channel_a", "val_a")]

        await checkpointer.aput_writes(config, writes, task_id="task_1")

        assert mock_redis.set.call_count == 1
        call_args = mock_redis.set.call_args_list[0]
        assert call_args[0][0] == "gaiaos:checkpoint:test_thread_123:writes:chk_001:task_1"
        assert call_args[1]["ex"] == 1800

    @pytest.mark.asyncio
    async def test_aput_disabled_ttl(self) -> None:
        """aput with ttl_seconds=0 does not pass ex parameter to set."""
        mock_redis = MagicMock()
        mock_redis.set = AsyncMock()

        checkpointer = RedisCheckpointSaver(mock_redis, ttl_seconds=0)

        config = {"configurable": {"thread_id": "test_thread_123"}}
        checkpoint = {"id": "chk_001"}

        await checkpointer.aput(config, checkpoint, metadata={}, new_versions={})  # type: ignore[arg-type]

        key_call, latest_call = mock_redis.set.call_args_list
        assert "ex" not in key_call[1]
        assert "ex" not in latest_call[1]


def _is_docker_redis_available() -> bool:
    """Check if docker CLI and running redis container are available."""
    try:
        res = subprocess.run(
            ["docker", "compose", "ps", "redis"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        return res.returncode == 0 and "redis" in res.stdout
    except Exception:
        return False


async def _wait_for_redis_ready(redis_url: str, timeout: float = 30.0) -> None:
    """Poll Redis until PING succeeds or timeout expires."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            ping_client = redis.asyncio.Redis.from_url(redis_url)
            if await ping_client.ping():
                await ping_client.aclose()
                return
            await ping_client.aclose()
        except Exception:
            pass
        await asyncio.sleep(0.2)
    raise TimeoutError(
        f"Redis service at {redis_url} did not become ready within {timeout} seconds."
    )


class TestRedisPersistenceIntegration:
    """Integration tests for Redis AOF persistence across container restarts."""

    @pytest.mark.integration
    @pytest.mark.skipif(
        not _is_docker_redis_available() or not os.getenv("REDIS_URL"),
        reason="Requires running Docker compose Redis container and REDIS_URL environment variable",
    )
    @pytest.mark.asyncio
    async def test_redis_aof_persistence_across_container_restart(self) -> None:
        """Verify checkpoint data survives a Docker container restart via AOF persistence."""
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        client = redis.asyncio.Redis.from_url(redis_url)
        saver = RedisCheckpointSaver(client, ttl_seconds=3600)

        thread_id = f"test_aof_restart_{uuid.uuid4()}"
        config = cast(
            RunnableConfig,
            {"configurable": {"thread_id": thread_id}},
        )

        checkpoint = cast(
            Checkpoint,
            {"id": "chk_aof_01", "ts": "2026-07-24T12:00:00Z", "v": 1},
        )

        metadata = cast(
            CheckpointMetadata,
            {"source": "aof_test"},
        )

        # 1. Write checkpoint
        await saver.aput(config, checkpoint, metadata, new_versions={})

        # Verify initial write
        fetched = await saver.aget_tuple(config)
        assert fetched is not None
        assert fetched.checkpoint["id"] == "chk_aof_01"
        await client.aclose()

        # 2. Restart Redis container via Docker Compose
        restart_res = subprocess.run(
            ["docker", "compose", "restart", "redis"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert restart_res.returncode == 0, f"Docker restart failed: {restart_res.stderr}"

        # Bounded readiness wait polling Redis PING up to 30s
        await _wait_for_redis_ready(redis_url, timeout=30.0)

        # 3. Reconnect and verify data survived container restart
        new_client = redis.asyncio.Redis.from_url(redis_url)
        new_saver = RedisCheckpointSaver(new_client, ttl_seconds=3600)

        resurrected = await new_saver.aget_tuple(config)
        assert resurrected is not None
        assert resurrected.checkpoint["id"] == "chk_aof_01"

        await new_client.aclose()
