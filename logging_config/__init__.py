"""Logging configuration package.

Public surface
--------------
``configure_logging(settings)``
    Call once at application startup, before any logger is used.
    Configures both ``structlog`` and the standard library ``logging``
    module so that all log output is consistent and environment-aware.

``get_logger(*args, **kwargs)``
    The only way any module in this project should obtain a logger.
    Delegates to ``structlog.get_logger()`` so loggers are always bound
    to the configured processors and renderers.

Usage
-----
In any module that needs to log::

    from logging_config import get_logger

    log = get_logger(__name__)
    log.info("something happened", key="value")

Import direction (enforced, no cycles):
    logging_config → structlog, logging (stdlib only)
    app            → logging_config
    gateway        → logging_config
    db             → logging_config
    logging_config ✗→ app, gateway, db, config  (never)
"""

import structlog

from logging_config.setup import configure_logging

get_logger = structlog.get_logger

__all__ = [
    "configure_logging",
    "get_logger",
]
