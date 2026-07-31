"""Unit tests for PostgreSQL read-replica engine initialization and transparent fallback."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

import db.session as db_session
from config.settings import get_settings
from db.session import (
    dispose_engine,
    get_read_session,
    init_engine,
)

pytestmark = pytest.mark.asyncio


class TestReadReplicaSession:
    """Test suite for read-replica initialization, cleanup, and primary fallback."""

    async def test_unconfigured_replica_uses_primary_factory(self, monkeypatch) -> None:
        """When replica is None, AsyncReadSessionLocal equals AsyncSessionLocal."""
        settings = get_settings()
        monkeypatch.setattr(settings, "read_replica_database_url", None)

        init_engine()
        try:
            assert db_session.AsyncSessionLocal is not None
            assert db_session.AsyncReadSessionLocal is db_session.AsyncSessionLocal
            assert db_session.read_engine is None
        finally:
            await dispose_engine()

    async def test_configured_replica_initializes_separate_engine(self, monkeypatch) -> None:
        """When READ_REPLICA_DATABASE_URL is set, a distinct read_engine is created."""
        settings = get_settings()
        replica_url = "postgresql://replica_user:pass@localhost:5432/gaiaos_replica"
        monkeypatch.setattr(settings, "read_replica_database_url", replica_url)

        init_engine()
        try:
            assert db_session.AsyncSessionLocal is not None
            assert db_session.AsyncReadSessionLocal is not None
            assert db_session.AsyncReadSessionLocal is not db_session.AsyncSessionLocal
            assert db_session.read_engine is not None
            assert db_session.read_engine is not db_session.engine
        finally:
            await dispose_engine()

    async def test_replica_operational_error_falls_back_to_primary(self, monkeypatch) -> None:
        """OperationalError on read replica triggers transparent fallback to primary."""
        settings = get_settings()
        replica_url = "postgresql://replica_user:pass@localhost:5432/gaiaos_replica"
        monkeypatch.setattr(settings, "read_replica_database_url", replica_url)

        init_engine()
        try:
            # Mock AsyncReadSessionLocal to raise OperationalError on session context entry
            mock_replica_session = AsyncMock()
            mock_replica_session.__aenter__.side_effect = OperationalError(
                statement="SELECT 1", params={}, orig=Exception("Connection refused")
            )
            mock_replica_factory = MagicMock(return_value=mock_replica_session)
            monkeypatch.setattr(db_session, "AsyncReadSessionLocal", mock_replica_factory)

            # Mock AsyncSessionLocal to return a valid mock session
            mock_primary_session = AsyncMock(spec=AsyncSession)
            mock_primary_factory = MagicMock()
            mock_primary_factory.return_value.__aenter__.return_value = mock_primary_session
            monkeypatch.setattr(db_session, "AsyncSessionLocal", mock_primary_factory)

            sessions = []
            async for s in get_read_session():
                sessions.append(s)

            assert len(sessions) == 1
            assert sessions[0] is mock_primary_session
        finally:
            await dispose_engine()

    async def test_configured_replica_success_uses_replica_factory(self, monkeypatch) -> None:
        """When replica is configured and acquisition succeeds, primary is never called."""
        settings = get_settings()
        replica_url = "postgresql://replica_user:pass@localhost:5432/gaiaos_replica"
        monkeypatch.setattr(settings, "read_replica_database_url", replica_url)

        init_engine()
        try:
            mock_replica_session = AsyncMock(spec=AsyncSession)
            mock_replica_factory = MagicMock()
            mock_replica_factory.return_value.__aenter__.return_value = mock_replica_session
            monkeypatch.setattr(db_session, "AsyncReadSessionLocal", mock_replica_factory)

            mock_primary_factory = MagicMock()
            monkeypatch.setattr(db_session, "AsyncSessionLocal", mock_primary_factory)

            sessions = []
            async for s in get_read_session():
                sessions.append(s)

            assert len(sessions) == 1
            assert sessions[0] is mock_replica_session
            mock_primary_factory.assert_not_called()
        finally:
            await dispose_engine()
