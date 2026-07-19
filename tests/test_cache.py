"""Unit and integration tests for Redis connection layer and key builder."""

from __future__ import annotations

import os

import pytest
from pydantic import ValidationError

from cache.client import dispose_redis, get_redis, init_redis
from cache.keys import RedisKeyBuilder
from config.settings import Settings


class TestRedisKeyBuilder:
    """Test standard namespaced Redis key formatting."""

    def test_cache_key_prefix(self) -> None:
        key = RedisKeyBuilder.cache_key("test_key")
        assert key == "gaiaos:cache:test_key"

    def test_checkpoint_key_prefix(self) -> None:
        key = RedisKeyBuilder.checkpoint_key("thread_123")
        assert key == "gaiaos:checkpoint:thread_123"

    def test_rate_limit_key_prefix(self) -> None:
        key = RedisKeyBuilder.rate_limit_key("127.0.0.1", "search")
        assert key == "gaiaos:ratelimit:127.0.0.1:search"


class TestRedisSettingsValidation:
    """Test validation settings rules for REDIS_URL."""

    def test_redis_url_optional_in_dev(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GAIAOS_ENV", "dev")
        monkeypatch.delenv("REDIS_URL", raising=False)
        settings = Settings(_env_file=None)  # type: ignore[call-arg]
        assert settings.redis_url is None

    def test_redis_url_required_in_staging(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GAIAOS_ENV", "staging")
        monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
        monkeypatch.delenv("REDIS_URL", raising=False)
        with pytest.raises(ValidationError, match="REDIS_URL must be set"):
            Settings(_env_file=None)  # type: ignore[call-arg]

    def test_redis_url_required_in_prod(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GAIAOS_ENV", "prod")
        monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
        monkeypatch.setenv("ENABLE_AUTH", "True")
        monkeypatch.delenv("REDIS_URL", raising=False)
        with pytest.raises(ValidationError, match="REDIS_URL must be set"):
            Settings(_env_file=None)  # type: ignore[call-arg]


class TestRedisConnectionLifecycle:
    """Integration tests for connection and lifecycle management."""

    async def test_lifecycle_success(self) -> None:
        """Test connection starts, ping succeeds, and disposes cleanly."""
        redis_url = os.environ.get("REDIS_URL")
        if not redis_url:
            pytest.skip("REDIS_URL environment variable is not set — skipping integration test.")

        settings = Settings(_env_file=None)
        settings.redis_url = redis_url

        # Initialise
        await init_redis(settings)
        client = await get_redis()

        # Ping check
        pong = await client.ping()
        assert pong is True

        # Dispose
        await dispose_redis()
        with pytest.raises(RuntimeError, match="client is not initialised"):
            await get_redis()

    async def test_failure_path_unreachable(self) -> None:
        """Test init_redis raises error when pointing to unreachable server."""
        settings = Settings(_env_file=None)
        settings.redis_url = "redis://localhost:9999/0"

        with pytest.raises(RuntimeError, match="Failed to connect to Redis"):
            await init_redis(settings)
