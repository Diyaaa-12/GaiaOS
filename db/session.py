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

from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from config.settings import get_settings

# Module-level singletons — initialised by init_engine(), disposed by
# dispose_engine().  Both are called from app.main's lifespan handler.
engine: AsyncEngine | None = None
AsyncSessionLocal: async_sessionmaker[AsyncSession] | None = None


def init_engine() -> None:
    """Create the async engine and session factory.

    Must be called once during application startup (lifespan).
    Idempotent: subsequent calls replace the existing engine reference,
    so callers must not hold references to the old engine.

    Raises ``RuntimeError`` if ``DATABASE_URL`` is not configured.
    """
    global engine, AsyncSessionLocal

    settings = get_settings()
    if settings.database_url is None:
        raise RuntimeError(
            "DATABASE_URL is not set.  "
            "The database connection layer cannot be initialised without it."
        )

    engine = create_async_engine(
        settings.asyncpg_url,
        # Replace stale connections transparently.
        pool_pre_ping=True,
        # Pool sizing: 5 connections idle + 10 overflow = 15 max concurrent.
        # These are conservative defaults appropriate for a single-instance
        # dev/staging deployment; tune via env vars in later milestones.
        pool_size=5,
        max_overflow=10,
        # SQL query logging is now controlled by the stdlib logging bridge
        # configured in logging_config.setup.configure_logging().
        # Set LOG_LEVEL=DEBUG to see all queries; higher levels suppress them.
        # echo=False prevents SQLAlchemy from bypassing the logging bridge
        # with its own raw stdout writes.
        echo=False,
    )

    AsyncSessionLocal = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        # expire_on_commit=False prevents SQLAlchemy from expiring all
        # attributes after a commit, which would cause lazy-load attempts
        # on detached instances in response serialisation.
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


async def dispose_engine() -> None:
    """Dispose the connection pool and release all connections.

    Must be called during application shutdown (lifespan).
    Safe to call even if ``init_engine()`` was never called.

    Nulls both ``engine`` and ``AsyncSessionLocal`` so any post-shutdown
    access to ``get_db_session`` raises a clear ``RuntimeError`` rather
    than attempting to use a factory whose underlying engine is gone.
    """
    global engine, AsyncSessionLocal
    if engine is not None:
        await engine.dispose()
        engine = None
    AsyncSessionLocal = None


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session and guarantee cleanup.

    Intended for use as a FastAPI dependency via ``app.dependencies``.
    Callers are responsible for calling ``session.commit()`` or
    ``session.rollback()`` explicitly; this generator only guarantees
    the session is closed.

    Raises ``RuntimeError`` if the session factory has not been initialised
    (i.e. ``init_engine()`` was never called).

    Example::

        @router.get("/example")
        async def example(db: DbSessionDep) -> ...:
            result = await db.execute(select(MyModel))
            ...
    """
    if AsyncSessionLocal is None:
        raise RuntimeError(
            "Database session factory is not initialised.  "
            "Ensure init_engine() is called during application startup."
        )

    async with AsyncSessionLocal() as session:
        yield session


async def verify_extensions(session: AsyncSession) -> dict[str, bool]:
    """Check that PostGIS and pgvector are installed in the database.

    Queries ``pg_extension`` — a read-only catalog view available to any
    database user.  Does NOT attempt to create extensions.

    Returns a dict mapping extension name to a boolean indicating presence.
    Raises ``sqlalchemy.exc.OperationalError`` on connection failure.
    """
    result = await session.execute(
        text("SELECT extname FROM pg_extension WHERE extname IN ('postgis', 'vector')")
    )
    installed: set[str] = {row[0] for row in result}
    return {
        "postgis": "postgis" in installed,
        "vector": "vector" in installed,
    }


__all__ = [
    "AsyncSessionLocal",
    "engine",
    "get_db_session",
    "init_engine",
    "dispose_engine",
    "verify_extensions",
]
