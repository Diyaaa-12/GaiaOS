"""Shared pytest fixtures for the GaiaOS test suite.

Fixture overview
----------------
``settings``
    Session-scoped Settings object loaded from the current environment.
    Immutable after construction — safe to share across all tests.

``db_session``
    Function-scoped async session connected to the real test database.
    Uses ``NullPool`` so asyncpg makes no connection-pool assumptions and
    every connection is fully opened and closed within a single test's event
    loop.  This is the correct pattern for asyncio tests in Python 3.12+.

``app``
    Function-scoped FastAPI application instance with a full lifespan.
    ``init_engine()`` runs on startup; ``dispose_engine()`` runs on teardown.
    Function-scoped so each test gets its own clean connection lifecycle.

``client``
    Function-scoped ``httpx.AsyncClient`` bound to the ``app`` via
    ``ASGITransport``.  Exercises the full ASGI stack (middleware included).

Why NullPool?
-------------
asyncpg maintains a pool that holds open TCP connections.  When pytest-asyncio
creates a fresh event loop per test (the default), those connections were
created on a *previous* loop.  asyncpg then fails with:
    "is bound to a different event loop"
Using ``NullPool`` disables all pooling — each execute() call opens and closes
a connection within the same event loop.  This adds ~5ms per query in tests
but eliminates all loop-mismatch errors without any pytest-asyncio hacks.

Requirement
-----------
``DATABASE_URL`` must be set in the environment before running tests.
The simplest way on a developer machine is to expose the Docker Compose
Postgres service on localhost (see README § Local Testing):

    $env:DATABASE_URL = "postgresql://gaiaos:gaiaos_dev_password@localhost:5432/gaiaos"
    pytest
"""

from __future__ import annotations

import os

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.main import create_app
from config.settings import Settings
from db.session import _asyncpg_url


# ---------------------------------------------------------------------------
# Settings fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def settings() -> Settings:
    """Return application settings loaded from the current environment.

    Session-scoped — Settings is constructed once from environment variables
    and is effectively immutable for the duration of the test session.
    """
    return Settings()


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def db_session() -> AsyncSession:  # type: ignore[misc]
    """Yield a fresh async session for each test against the real database.

    Uses ``NullPool`` to avoid connection-pool state being shared across
    test event loops.  Each connection is opened and closed within the
    single test's event loop, which is the correct approach for asyncio
    tests in Python 3.12+.

    Skips the test if ``DATABASE_URL`` is not set, with a clear message.
    """
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        pytest.skip(
            "DATABASE_URL is not set — skipping database tests.  "
            "Set DATABASE_URL to a running PostgreSQL instance before running pytest."
        )

    async_url = _asyncpg_url(database_url)
    # NullPool: no connection is retained after the session closes.
    # This prevents "bound to a different event loop" errors because no
    # asyncpg connection object outlives the test's event loop.
    engine = create_async_engine(async_url, poolclass=NullPool)
    factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    async with factory() as session:
        yield session

    await engine.dispose()


# ---------------------------------------------------------------------------
# Application and HTTP client fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def app():  # type: ignore[misc]
    """Create the FastAPI application and run its full lifespan per test.

    Function-scoped so each test that needs the application gets a clean
    engine lifecycle.  The lifespan calls ``init_engine()`` and runs the
    startup DB extension checks against the real database.

    Skips the test if ``DATABASE_URL`` is not set.
    """
    if not os.environ.get("DATABASE_URL"):
        pytest.skip(
            "DATABASE_URL is not set — skipping application tests.  "
            "Set DATABASE_URL to a running PostgreSQL instance before running pytest."
        )

    application = create_app()

    # Drive the lifespan manually so startup/shutdown hooks run exactly as in
    # production.  The lifespan calls init_engine() (creates the pool) on
    # startup and dispose_engine() (closes the pool) on teardown.
    async with application.router.lifespan_context(application):
        yield application


@pytest.fixture
async def client(app) -> AsyncClient:  # type: ignore[misc]
    """Yield an async HTTP client wired to the running application.

    Uses ``httpx.AsyncClient`` with ``ASGITransport`` so requests go through
    the full ASGI stack (middleware included) without a real TCP socket.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac
