"""Persistent RQ Scheduler service for GaiaOS automated background jobs."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from redis import Redis
from rq_scheduler import Scheduler  # type: ignore[import-untyped]

from config.settings import get_settings
from logging_config import configure_logging, get_logger

_log = get_logger(__name__)


def is_job_already_scheduled(scheduler: Scheduler, func_name: str, source: str) -> bool:
    """Check if a recurring job with given func_name and source is already scheduled."""
    try:
        jobs = scheduler.get_jobs()
        for job in jobs:
            if job.func_name == func_name and job.args and job.args[0] == source:
                return True
    except Exception as e:
        _log.warning("scheduler.check_jobs_failed", error=str(e))
    return False


def main() -> None:
    """Initialize Redis connection, start RQ Scheduler, and register idempotent recurring jobs."""
    settings = get_settings()
    configure_logging(settings)

    redis_url = settings.redis_url or "redis://localhost:6379/0"
    _log.info("scheduler.starting", redis_url=redis_url)

    connection = Redis.from_url(redis_url)
    scheduler = Scheduler(connection=connection)

    interval_seconds = settings.ingestion_poll_interval_hours * 3600
    target_func = "workers.jobs.ingestion_jobs.run_ingestion_job"

    # Idempotent scheduling for USGS and NOAA sources
    for source in ["usgs", "noaa"]:
        if is_job_already_scheduled(scheduler, target_func, source):
            _log.info("scheduler.job_exists_skipping", source=source)
        else:
            _log.info("scheduler.registering_job", source=source, interval_seconds=interval_seconds)
            scheduler.schedule(
                scheduled_time=datetime.now(UTC) + timedelta(seconds=10),
                func=target_func,
                args=[source],
                interval=interval_seconds,
                repeat=None,  # Infinite recurrence
            )

    _log.info("scheduler.running")
    scheduler.run()


if __name__ == "__main__":
    main()
