"""RQ Worker process entry point for GaiaOS."""

from __future__ import annotations

from redis import Redis
from rq import Worker

import db.session as db_session
from config.settings import get_settings
from logging_config import configure_logging, get_logger

_log = get_logger(__name__)


def main() -> None:
    """Initialize configuration, DB pool, Redis connection, and start RQ worker process."""
    settings = get_settings()
    configure_logging(settings)

    if settings.database_url:
        db_session.init_engine()
        _log.info("worker.db.initialized")

    redis_url = settings.redis_url or "redis://localhost:6379/0"
    _log.info("worker.starting", redis_url=redis_url, queue="default")

    connection = Redis.from_url(redis_url)
    worker = Worker(["default"], connection=connection)
    worker.work(with_scheduler=False)


if __name__ == "__main__":
    main()
