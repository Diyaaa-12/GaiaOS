"""Alembic migration environment for GaiaOS.

Architecture overview
---------------------
GaiaOS uses SQLAlchemy's async engine (asyncpg driver).  Alembic's own
migration runner is synchronous, so we use the standard adapter pattern:

1.  Build a *synchronous* connection URL by swapping the async driver prefix
    back to plain ``postgresql+psycopg2`` — **but** because we don't want
    to add a second driver dependency, we use SQLAlchemy's
    ``create_engine`` with a *synchronous* URL derived from the async URL.

    Actually, the cleanest zero-extra-dependency approach is:
    - Keep asyncpg for the app.
    - Use Alembic's ``run_sync`` helper via an ``AsyncEngine.sync_engine``
      facade — available since SQLAlchemy 1.4 / Alembic 1.7.

2.  ``target_metadata`` is set to ``Base.metadata`` from ``db.base``.
    ``db.base`` has no upstream project-level imports (only SQLAlchemy),
    so importing it here creates zero circular dependency risk.

3.  The database URL is read from the environment via ``config.settings``,
    exactly as the application does.  No credentials live in ``alembic.ini``.

Import graph (no cycles):
    data/migrations/env.py
        → db.base          (Base.metadata — SQLAlchemy only)
        → config.settings  (DATABASE_URL — pydantic-settings only)
        ✗ → db.session     (not imported; no engine singletons needed here)
        ✗ → app.*          (never imported from migration environment)
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from config.settings import get_settings
from db.base import Base

# ---------------------------------------------------------------------------
# Alembic Config object — gives access to values in alembic.ini.
# ---------------------------------------------------------------------------
config = context.config

# Set up Python logging from the [loggers] section in alembic.ini,
# but only when a config file is present (it may be None in programmatic use).
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------------
# Target metadata — the single source of truth for autogenerate.
#
# All ORM models must be imported *before* this line is reached so that
# their Table objects are registered in Base.metadata.  In later milestones,
# add model imports here as they are created.  For Milestone 6 there are no
# ORM models yet; Base.metadata is intentionally empty.
# ---------------------------------------------------------------------------
target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

def _get_async_url() -> str:
    """Return the async-driver database URL for use by the async engine.

    Reads DATABASE_URL from settings (which reads from the environment / .env)
    and rewrites the scheme to ``postgresql+asyncpg://`` if necessary — the
    same logic as ``db.session._asyncpg_url()``.

    Raises ``RuntimeError`` if DATABASE_URL is not set.
    """
    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError(
            "DATABASE_URL is not set.  "
            "Export it or add it to your .env file before running Alembic."
        )

    url: str = settings.database_url
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+asyncpg://" + url[len(prefix):]

    if url.startswith("postgresql+asyncpg://"):
        return url

    raise RuntimeError(
        f"DATABASE_URL must start with postgresql:// or postgres://; got: {url!r}"
    )


# ---------------------------------------------------------------------------
# Offline migration mode
# ---------------------------------------------------------------------------

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL to stdout, no DB connection).

    This is useful for generating a SQL script to review or apply manually.
    Invoke with: ``alembic upgrade head --sql``
    """
    url = _get_async_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Emit a transaction per migration so the script is
        # safe to apply incrementally.
        transaction_per_migration=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online migration mode
# ---------------------------------------------------------------------------

def do_run_migrations(connection) -> None:  # type: ignore[type-arg]
    """Execute migrations with a live synchronous connection.

    Called by ``run_migrations_online`` inside ``run_sync``.
    The connection is the sync facade of the async engine's connection.
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # Compare server defaults so autogenerate catches DEFAULT changes.
        compare_server_defaults=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create a temporary async engine, obtain a sync connection facade, and
    run migrations.

    We create a *new* engine here (separate from the application's singleton
    in ``db.session``) to keep the migration environment fully self-contained
    and avoid any dependency on the app lifespan.

    ``NullPool`` is used so Alembic does not hold idle connections after the
    migration run completes — important in CI pipelines and short-lived
    ``alembic`` CLI invocations.
    """
    connectable = create_async_engine(
        _get_async_url(),
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online (connected) migration mode."""
    asyncio.run(run_async_migrations())


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
