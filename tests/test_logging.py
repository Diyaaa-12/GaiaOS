import logging

import pytest
import structlog

from config.settings import Settings
from logging_config.setup import configure_logging


def test_dev_environment_selects_console_renderer(monkeypatch: pytest.MonkeyPatch):
    """Verify that GAIAOS_ENV=dev selects ConsoleRenderer."""
    monkeypatch.setenv("GAIAOS_ENV", "dev")
    settings = Settings(_env_file=None)
    configure_logging(settings)

    root_logger = logging.getLogger()
    assert len(root_logger.handlers) > 0
    formatter = root_logger.handlers[0].formatter

    # The final renderer is the last processor in the formatter's processor list
    final_renderer = formatter.processors[-1]
    assert isinstance(final_renderer, structlog.dev.ConsoleRenderer)


def test_prod_environment_selects_json_renderer(monkeypatch: pytest.MonkeyPatch):
    """Verify that GAIAOS_ENV=prod selects JSONRenderer."""
    monkeypatch.setenv("GAIAOS_ENV", "prod")
    monkeypatch.setenv("DATABASE_URL", "postgresql://dummy")
    monkeypatch.setenv("REDIS_URL", "redis://dummy")
    monkeypatch.setenv("ENABLE_AUTH", "True")
    settings = Settings(_env_file=None)
    configure_logging(settings)

    root_logger = logging.getLogger()
    assert len(root_logger.handlers) > 0
    formatter = root_logger.handlers[0].formatter

    final_renderer = formatter.processors[-1]
    assert isinstance(final_renderer, structlog.processors.JSONRenderer)


def test_logging_configuration_initializes_correctly(monkeypatch: pytest.MonkeyPatch):
    """Verify logging sets the correct log level and doesn't duplicate handlers."""
    # Ensure starting clean
    logging.getLogger().handlers.clear()

    monkeypatch.setenv("GAIAOS_ENV", "dev")
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    settings = Settings(_env_file=None)
    configure_logging(settings)

    root_logger = logging.getLogger()
    assert len(root_logger.handlers) == 1
    assert root_logger.level == logging.INFO

    # Calling it twice should clear and recreate the handler, remaining at 1
    configure_logging(settings)
    assert len(root_logger.handlers) == 1
