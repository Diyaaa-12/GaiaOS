"""Structured logging configuration for GaiaOS.

This is the single, authoritative logging configuration for the entire
application.  It must be called exactly once at startup, before any logger
is used, to guarantee consistent output across all layers.

Architecture
------------
structlog is configured with a shared processor chain:

  1. Add log level name.
  2. Add ISO-8601 timestamp.
  3. Add caller information (module, function, line).
  4. Render with an environment-aware renderer:
       - dev          → ConsoleRenderer   (human-readable, coloured in terminal)
       - staging/prod → JSONRenderer      (machine-parseable, one line per event)

The standard library ``logging`` module is also configured via
``structlog.stdlib.ProcessorFormatter`` so that third-party libraries
(SQLAlchemy, uvicorn, asyncpg, alembic) that emit stdlib log records are
rendered through the same pipeline.  This means a single log level setting
controls everything.

Security
--------
This module intentionally does NOT log:
- Request bodies
- Authorization headers
- Passwords or tokens

These are never passed to any logger.  The extension point for controlled
request-body logging in a future milestone is the gateway middleware — add
a processor or a dedicated hook there with appropriate redaction, not here.

Duplicate handler prevention
-----------------------------
``configure_logging`` is idempotent: calling it more than once (e.g. in
tests) replaces the existing configuration safely because ``structlog``
overwrites its global configuration and stdlib's ``logging.root`` handlers
are cleared before new ones are added.
"""

from __future__ import annotations

import logging
import logging.config
import sys
from typing import TYPE_CHECKING

import structlog
from structlog.types import Processor

if TYPE_CHECKING:
    from config.settings import Settings


# ---------------------------------------------------------------------------
# Shared processor chain (environment-independent)
# ---------------------------------------------------------------------------


def _shared_processors() -> list[Processor]:
    """Return the processor chain that runs for every log event.

    These processors run before the final renderer so they are common to
    both the dev (human-readable) and prod (JSON) pipelines.
    """
    return [
        # Merge in values from any bound context (e.g. request_id).
        structlog.contextvars.merge_contextvars,
        # Add the log level name ("info", "warning", etc.).
        structlog.stdlib.add_log_level,
        # Add an ISO-8601 timestamp.
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        # Add the call site (module, function, line number) for DEBUG logs.
        structlog.processors.CallsiteParameterAdder(
            [
                structlog.processors.CallsiteParameter.MODULE,
                structlog.processors.CallsiteParameter.FUNC_NAME,
                structlog.processors.CallsiteParameter.LINENO,
            ]
        ),
    ]


# ---------------------------------------------------------------------------
# Public configuration entry point
# ---------------------------------------------------------------------------


def configure_logging(settings: Settings) -> None:
    """Configure structlog and the stdlib logging module.

    Must be called once at application startup (in ``app.main.create_app``)
    before any logger is obtained or used.  Calling it multiple times is
    safe — subsequent calls replace the previous configuration.

    Parameters
    ----------
    settings:
        The application settings object.  Uses ``gaiaos_env`` to choose the
        renderer and ``log_level`` to set the minimum log level.

    Renderer selection:
        ``gaiaos_env == "dev"``            → ConsoleRenderer (human-readable)
        ``gaiaos_env in ("staging","prod")`` → JSONRenderer  (machine-parseable)
    """
    log_level_name: str = settings.log_level.upper()
    log_level: int = getattr(logging, log_level_name, logging.DEBUG)
    is_dev: bool = settings.gaiaos_env == "dev"

    # Choose the final renderer based on environment.
    if is_dev:
        # Human-readable, coloured output for local development.
        # colours=True only if stdout is a real terminal; safe in Docker.
        final_renderer: Processor = structlog.dev.ConsoleRenderer(
            colors=sys.stdout.isatty(),
        )
    else:
        # One JSON object per line — consumed by log aggregation platforms.
        final_renderer = structlog.processors.JSONRenderer()

    # --- Configure structlog ---
    structlog.configure(
        processors=[
            *_shared_processors(),
            # Prepare the event dict for the stdlib ProcessorFormatter used
            # by the stdlib handler below, so third-party library logs also
            # flow through the shared chain.
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        # Use the stdlib logger as the underlying logger so structlog events
        # and stdlib events share the same handler/sink.
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        cache_logger_on_first_use=True,
    )

    # --- Configure the stdlib formatter that wraps the shared chain ---
    formatter = structlog.stdlib.ProcessorFormatter(
        # Processors that run *after* the event reaches the stdlib handler
        # (i.e. on the stdlib side of the bridge, for third-party log records).
        processors=[
            # Extract any structlog context from the stdlib record.
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            final_renderer,
        ],
        # Processors that run *before* the stdlib record is handed off
        # (common to both structlog-native and stdlib-originated records).
        foreign_pre_chain=_shared_processors(),
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.setLevel(log_level)

    # --- Apply to the root logger ---
    # Clear any existing handlers first to avoid duplicates on re-configuration
    # (important in tests that call configure_logging more than once).
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # --- Silence overly chatty third-party loggers ---
    # uvicorn's access logger produces its own per-request lines; we emit our
    # own structured access log in the gateway middleware instead.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    # SQLAlchemy engine echo is controlled by the engine's own ``echo`` flag
    # (set to False in db.session.init_engine after this milestone).
    # The sqlalchemy.engine logger is left at root level so explicit
    # SQLAlchemy warnings and errors surface, but routine query statements
    # are suppressed unless LOG_LEVEL=DEBUG is set intentionally.
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.DEBUG if log_level <= logging.DEBUG else logging.WARNING
    )


__all__ = ["configure_logging"]
