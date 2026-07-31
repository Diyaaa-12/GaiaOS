"""RQ Worker process entry point for GaiaOS."""

from __future__ import annotations

from redis import Redis
from rq import Worker

import db.session as db_session
from config.settings import get_settings
from logging_config import configure_logging, get_logger

_log = get_logger(__name__)


def initialize_plugins() -> None:
    """Discover, validate, and register external agent plugins at worker startup.

    If strict_plugin_validation is True, any plugin loading error aborts worker boot.
    Otherwise, faulty plugins are disabled with a loud log message while worker boot continues.
    """
    settings = get_settings()
    if not settings.plugins_enabled:
        _log.info("worker.plugins_disabled_by_settings")
        return

    from orchestrator.agents.plugin_loader import (
        PluginValidationError,
        discover_plugins,
        load_and_validate_plugin,
        record_installed_plugin_telemetry_batch,
    )
    from orchestrator.agents.registry import agent_registry
    from orchestrator.schemas.plugin_manifest import PluginManifest

    discovered = discover_plugins()
    registered_count = 0
    telemetry_records: list[tuple[PluginManifest, str, str | None]] = []

    for manifest, runner_obj in discovered:
        try:
            runner = load_and_validate_plugin(manifest, runner_obj)
            agent_registry.register_plugin(manifest, runner)
            telemetry_records.append((manifest, "active", None))
            registered_count += 1
            _log.info(
                "worker.plugin_registered",
                name=manifest.name,
                domain=manifest.domain,
                version=manifest.version,
            )
        except Exception as e:
            telemetry_records.append((manifest, "failed", str(e)))
            _log.error(
                "worker.plugin_failed_disabled",
                name=manifest.name,
                domain=manifest.domain,
                error=str(e),
            )
            if settings.strict_plugin_validation:
                raise PluginValidationError(
                    f"Plugin '{manifest.name}' failed validation in strict mode: {e}"
                ) from e

    if telemetry_records:
        import asyncio

        try:
            asyncio.run(record_installed_plugin_telemetry_batch(telemetry_records))
        except Exception as exc:
            _log.warning("worker.telemetry_batch_failed", error=str(exc))

    _log.info("worker.plugins_initialized", count=registered_count)


def main() -> None:
    """Initialize configuration, DB pool, Redis connection, plugins, and start RQ worker process."""
    settings = get_settings()
    configure_logging(settings)

    if settings.database_url:
        db_session.init_engine()
        _log.info("worker.db.initialized")

    # Discover and register dynamic agent plugins
    initialize_plugins()

    redis_url = settings.redis_url or "redis://localhost:6379/0"
    _log.info("worker.starting", redis_url=redis_url, queue="default")

    connection = Redis.from_url(redis_url)
    worker = Worker(["default"], connection=connection)
    worker.work(with_scheduler=False)


if __name__ == "__main__":
    main()
