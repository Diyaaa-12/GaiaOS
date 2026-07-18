"""Integration tests for database connectivity and extension verification.

Tests run against a real PostgreSQL database — no mocks.

Coverage
--------
- Database connection can be established and a trivial query executed.
- ``verify_extensions()`` reports PostGIS as present.
- ``verify_extensions()`` reports pgvector (``vector``) as present.
- ``verify_extensions()`` returns a complete dict with expected keys.

All tests use the ``db_session`` fixture from conftest.py, which creates a
fresh ``AsyncSession`` backed by the real PostgreSQL instance specified by
``DATABASE_URL``.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import verify_extensions


class TestDatabaseConnection:
    """Tests that verify the database connection is functional."""

    async def test_connection_is_alive(self, db_session: AsyncSession) -> None:
        """A simple SELECT 1 succeeds, confirming the connection is alive."""
        result = await db_session.execute(text("SELECT 1"))
        row = result.scalar_one()
        assert row == 1

    async def test_can_read_pg_version(self, db_session: AsyncSession) -> None:
        """SELECT version() returns a non-empty string."""
        result = await db_session.execute(text("SELECT version()"))
        version_string = result.scalar_one()
        assert isinstance(version_string, str)
        assert version_string  # non-empty
        assert "PostgreSQL" in version_string


class TestExtensionVerification:
    """Tests for ``db.session.verify_extensions()``.

    These tests reuse the existing helper rather than duplicating SQL.
    """

    async def test_verify_extensions_returns_dict(self, db_session: AsyncSession) -> None:
        """verify_extensions() returns a dict with the expected keys."""
        result = await verify_extensions(db_session)
        assert isinstance(result, dict)
        assert "postgis" in result
        assert "vector" in result

    async def test_postgis_is_installed(self, db_session: AsyncSession) -> None:
        """PostGIS extension is present in the test database."""
        result = await verify_extensions(db_session)
        assert result["postgis"] is True, (
            "PostGIS extension is not installed.  "
            "Ensure the database was initialised with init-extensions.sql."
        )

    async def test_pgvector_is_installed(self, db_session: AsyncSession) -> None:
        """pgvector (vector) extension is present in the test database."""
        result = await verify_extensions(db_session)
        assert result["vector"] is True, (
            "pgvector (vector) extension is not installed.  "
            "Ensure the database was initialised with init-extensions.sql."
        )

    async def test_all_required_extensions_present(self, db_session: AsyncSession) -> None:
        """All extensions required by Phase 1 are present and accounted for."""
        result = await verify_extensions(db_session)
        missing = [name for name, present in result.items() if not present]
        assert not missing, (
            f"Required PostgreSQL extensions are missing: {missing}.  "
            "Ensure the database was initialised with init-extensions.sql."
        )
