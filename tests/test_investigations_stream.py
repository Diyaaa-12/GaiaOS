"""Tests for the Server-Sent Events (SSE) streaming infrastructure."""

from __future__ import annotations

import asyncio
import os
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from cache.client import dispose_redis, init_redis, parse_event, publish_event, subscribe
from config.settings import Settings
from db.repository import InvestigationRepository
from orchestrator.schemas.events import PlanningData, PlanningEvent


class TestEventSerialization:
    """Verifies that events serialize and deserialize correctly."""

    def test_planning_event_serialization(self) -> None:
        event = PlanningEvent(data=PlanningData(status="planning"))
        serialized = event.model_dump_json()
        parsed = parse_event(serialized)
        assert parsed.event == "planning"
        assert parsed.data.status == "planning"


class TestStreamEndpoint:
    """Verifies HTTP SSE streaming endpoint routes, 404, and 503 errors."""

    async def _create_authenticated_user_and_headers(
        self,
        session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch | None = None,
    ):
        from auth.jwt_provider import create_access_token
        from auth.roles import Role
        from config.settings import get_settings
        from db.repository import UserRepository

        key = "super-secret-key-that-is-at-least-32-chars-long!"
        if monkeypatch is not None:
            monkeypatch.setenv("JWT_SECRET_KEY", key)
            get_settings.cache_clear()

        email = f"streamuser-{uuid.uuid4().hex[:6]}@example.com"
        user = await UserRepository.create_user(
            session=session,
            email=email,
            hashed_password="HashedPassword123!",
            role=Role.USER.value,
            is_verified=True,
        )
        token = create_access_token(user.id, user.role, secret_key=key)
        return user, {"Authorization": f"Bearer {token}"}

    @pytest.mark.asyncio
    async def test_stream_not_found(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _, headers = await self._create_authenticated_user_and_headers(db_session, monkeypatch)
        random_id = uuid.uuid4()
        response = await client.get(f"/api/v1/investigations/{random_id}/stream", headers=headers)
        assert response.status_code == 404
        assert response.json()["error_code"] == "investigation_not_found"

    @pytest.mark.asyncio
    async def test_stream_redis_unavailable(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        user, headers = await self._create_authenticated_user_and_headers(db_session, monkeypatch)
        # 1. Create a valid investigation in DB
        investigation = await InvestigationRepository.create_investigation(
            session=db_session,
            query="Test query",
            user_id=user.id,
        )

        # 2. Mock redis ping to fail (simulate Redis unavailable)
        with patch("redis.asyncio.Redis.ping", side_effect=RuntimeError("Redis down")):
            response = await client.get(
                f"/api/v1/investigations/{investigation.id}/stream", headers=headers
            )
            assert response.status_code == 503
            assert response.json()["error_code"] == "checkpointer_unavailable"

    @pytest.mark.asyncio
    async def test_stream_success_handshake(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        user, headers = await self._create_authenticated_user_and_headers(db_session, monkeypatch)
        # 1. Create a valid investigation in DB
        investigation = await InvestigationRepository.create_investigation(
            session=db_session,
            query="Test query",
            user_id=user.id,
        )

        # 2. Ensure Redis ping passes, and mock subscribe to yield immediately then close
        with patch("redis.asyncio.Redis.ping", new_callable=AsyncMock, return_value=True):
            # Mock the subscribe generator to yield a single event and then exit
            event = PlanningEvent(data=PlanningData(status="planning"))

            async def mock_sub(*args, **kwargs):
                yield event

            with patch("app.api.v1.investigations_stream.subscribe", new=mock_sub):
                # Request the SSE stream
                async with client.stream(
                    "GET",
                    f"/api/v1/investigations/{investigation.id}/stream",
                    headers=headers,
                ) as response:
                    assert response.status_code == 200
                    assert "text/event-stream" in response.headers["content-type"]

                    # Read first chunk
                    chunks = []
                    async for chunk in response.aiter_raw():
                        chunks.append(chunk)
                        if b"event: planning" in chunk:
                            break
                    assert any(b"event: planning" in c for c in chunks)


class TestRedisPubSubIntegration:
    """Verifies actual Redis Pub/Sub end-to-end integration when REDIS_URL is present."""

    @pytest.mark.asyncio
    async def test_pub_sub_integration_flow(self) -> None:
        redis_url = os.environ.get("REDIS_URL")
        if not redis_url:
            pytest.skip("REDIS_URL environment variable is not set — skipping integration test.")

        settings = Settings(_env_file=None)  # type: ignore[call-arg]

        settings.redis_url = redis_url

        await init_redis(settings)

        investigation_id = uuid.uuid4()
        event = PlanningEvent(data=PlanningData(status="planning"))

        # Subscribe iterator
        sub_iter = subscribe(investigation_id)

        # Publish after a short delay to simulate real timing
        async def publish_delayed():
            await asyncio.sleep(0.1)
            await publish_event(investigation_id, event)

        pub_task = asyncio.create_task(publish_delayed())

        received = []
        async for msg in sub_iter:
            received.append(msg)
            break  # Stop immediately to close stream and trigger finally block cleanup

        await pub_task
        await dispose_redis()

        assert len(received) == 1
        assert received[0].event == "planning"
        assert received[0].data.status == "planning"
