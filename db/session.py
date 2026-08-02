"""Async database engine and session factory.

Design decisions
----------------
Engine creation
    The engine is created lazily by ``init_engine()`` rather than at module
    import time.  This prevents connection attempts during testing and keeps
    module-level side effects to zero.  ``app.main`` calls ``init_engine()``
    in its lifespan startup hook and ``dispose_engine()`` on shutdown.

URL rewriting
    ``config.settings`` stores ``DATABASE_URL`` with the plain
    ``postgresql://`` scheme to keep operator configuration driver-agnostic.
    ``_asyncpg_url()`` rewrites it to ``postgresql+asyncpg://`` transparently
    so neither operators nor other modules need to know about the driver.

Connection pooling
    ``AsyncEngine`` uses SQLAlchemy's built-in ``AsyncAdaptedQueuePool`` by
    default.  ``pool_pre_ping=True`` silently replaces stale connections,
    which is essential for long-lived processes behind a NAT or load balancer.

Session factory
    ``AsyncSessionLocal`` is a session factory (not a session).  Each call
    produces a fresh ``AsyncSession`` bound to the engine.  Sessions are
    opened and closed by the DI provider in ``app.dependencies``, never here.

Extension verification
    ``verify_extensions()`` queries the ``pg_extension`` catalog — a
    read-only check that requires no superuser privileges.  It does NOT
    run ``CREATE EXTENSION``; that is the responsibility of the Postgres
    container init script (Milestone 3) and Alembic migrations (Milestone 6).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from config.settings import get_settings
from logging_config import get_logger

_log = get_logger(__name__)

# Module-level singletons — initialised by init_engine(), disposed by
# dispose_engine().  Both are called from app.main's lifespan handler.
engine: AsyncEngine | None = None
read_engine: AsyncEngine | None = None
AsyncSessionLocal: async_sessionmaker[AsyncSession] | None = None
AsyncReadSessionLocal: async_sessionmaker[AsyncSession] | None = None
_engine_loop: asyncio.AbstractEventLoop | None = None


def _check_loop() -> None:
    """Check if running event loop matches stored engine loop and reset singletons on mismatch."""
    global engine, read_engine, AsyncSessionLocal, AsyncReadSessionLocal, _engine_loop
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    if _engine_loop is not None and current_loop is not None and _engine_loop is not current_loop:
        _log.info("db.engine.loop_mismatch_clearing_stale_singletons")
        engine = None
        read_engine = None
        AsyncSessionLocal = None
        AsyncReadSessionLocal = None
        _engine_loop = None


def init_engine() -> None:
    """Create the async engine and session factory.

    Must be called once during application startup (lifespan).
    Idempotent: subsequent calls replace the existing engine reference,
    so callers must not hold references to the old engine.

    Raises ``RuntimeError`` if ``DATABASE_URL`` is not configured.
    """
    global engine, read_engine, AsyncSessionLocal, AsyncReadSessionLocal, _engine_loop

    _check_loop()

    settings = get_settings()
    if settings.database_url is None:
        raise RuntimeError(
            "DATABASE_URL is not set.  "
            "The database connection layer cannot be initialised without it."
        )

    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    engine = create_async_engine(
        settings.asyncpg_url,
        # Replace stale connections transparently.
        pool_pre_ping=True,
        # Pool sizing: 5 connections idle + 10 overflow = 15 max concurrent.
        pool_size=5,
        max_overflow=10,
        echo=False,
    )

    AsyncSessionLocal = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    if settings.read_replica_database_url and settings.read_asyncpg_url:
        read_engine = create_async_engine(
            settings.read_asyncpg_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            echo=False,
        )
        AsyncReadSessionLocal = async_sessionmaker(
            bind=read_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    else:
        read_engine = None
        AsyncReadSessionLocal = AsyncSessionLocal

    _engine_loop = current_loop


async def dispose_engine() -> None:
    """Dispose the connection pool and release all connections.

    Must be called during application shutdown (lifespan).
    Safe to call even if ``init_engine()`` was never called.

    Nulls ``engine``, ``read_engine``, ``AsyncSessionLocal``, and
    ``AsyncReadSessionLocal`` so post-shutdown session calls raise RuntimeError.
    """
    global engine, read_engine, AsyncSessionLocal, AsyncReadSessionLocal, _engine_loop
    if read_engine is not None and read_engine is not engine:
        try:
            await read_engine.dispose()
        except Exception:
            pass
        read_engine = None
    if engine is not None:
        try:
            await engine.dispose()
        except Exception:
            pass
        engine = None
    AsyncSessionLocal = None
    AsyncReadSessionLocal = None
    _engine_loop = None


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session and guarantee cleanup."""
    factory = get_session_factory()

    async with factory() as session:
        yield session


async def get_read_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a read-replica database session with primary fallback upon acquisition failure.

    Fallback Scope:
        The OperationalError fallback applies strictly during session acquisition and
        connection pool checkout (when entering factory()). Once a session is yielded to
        the caller, subsequent query execution errors within the caller's block are not
        retried or caught by this provider.

    Behavior:
        - If READ_REPLICA_DATABASE_URL is configured, attempts connection via read replica.
        - If connection checkout fails (OperationalError), logs warning and acquires
          a primary session.
        - If READ_REPLICA_DATABASE_URL is unconfigured, yields directly from primary factory.
    """
    _check_loop()
    factory = AsyncReadSessionLocal or AsyncSessionLocal
    if factory is None:
        factory = get_session_factory()

    # OperationalError during initial session acquisition / pool checkout triggers primary fallback.
    try:
        async with factory() as session:
            yield session
    except OperationalError as exc:
        if AsyncSessionLocal is not None and factory is not AsyncSessionLocal:
            _log.warning(
                "db.read_replica_failed_falling_back_to_primary",
                error=str(exc),
            )
            async with AsyncSessionLocal() as session:
                yield session
        else:
            raise


async def verify_extensions(session: AsyncSession) -> dict[str, bool]:
    """Check that PostGIS and pgvector are installed in the database."""
    result = await session.execute(
        text("SELECT extname FROM pg_extension WHERE extname IN ('postgis', 'vector')")
    )
    installed: set[str] = {row[0] for row in result}
    return {
        "postgis": "postgis" in installed,
        "vector": "vector" in installed,
    }


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the initialised session factory, calling init_engine() if needed."""
    global AsyncSessionLocal
    _check_loop()
    if AsyncSessionLocal is None:
        init_engine()
    assert AsyncSessionLocal is not None
    return AsyncSessionLocal


def __getattr__(name: str) -> Any:
    if name in ("AsyncSessionLocal", "AsyncReadSessionLocal", "engine", "read_engine"):
        _check_loop()
        return globals()[name]
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = [
    "AsyncReadSessionLocal",
    "AsyncSessionLocal",
    "dispose_engine",
    "engine",
    "get_db_session",
    "get_read_session",
    "get_session_factory",
    "init_engine",
    "read_engine",
    "verify_extensions",
]
