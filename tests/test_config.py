"""Unit tests for application configuration validation.

These tests exercise the ``Settings`` class from ``config.settings`` directly,
not through ``get_settings()``, so they do not touch the lru_cache and are
fully isolated from each other and from the running application.

Coverage
--------
- Default values are applied when environment variables are absent.
- ``GAIAOS_ENV`` accepts the documented literal values (dev/staging/prod).
- ``GAIAOS_ENV`` rejects undocumented values with a ValidationError.
- ``DATABASE_URL`` is required when ``GAIAOS_ENV`` is ``staging`` or ``prod``.
- ``DATABASE_URL`` is optional (may be ``None``) when ``GAIAOS_ENV`` is ``dev``.
- ``LOG_LEVEL`` defaults to ``"DEBUG"`` when not set.
- ``ENABLE_AUTH`` defaults to ``False`` when not set.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from config.settings import Settings


class TestSettingsDefaults:
    """Verify default values when no environment variables are set."""

    def test_gaiaos_env_defaults_to_dev(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """GAIAOS_ENV defaults to 'dev' when not set."""
        monkeypatch.delenv("GAIAOS_ENV", raising=False)
        # Construct Settings without an env file to avoid .env loading.
        settings = Settings(_env_file=None)  # type: ignore[call-arg]
        assert settings.gaiaos_env == "dev"

    def test_log_level_defaults_to_debug(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """LOG_LEVEL defaults to 'DEBUG' when not set."""
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        settings = Settings(_env_file=None)  # type: ignore[call-arg]
        assert settings.log_level == "DEBUG"

    def test_database_url_defaults_to_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """DATABASE_URL defaults to None in dev mode when not set."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.delenv("GAIAOS_ENV", raising=False)
        settings = Settings(_env_file=None)  # type: ignore[call-arg]
        assert settings.database_url is None

    def test_enable_auth_defaults_to_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """ENABLE_AUTH defaults to False when not set."""
        monkeypatch.delenv("ENABLE_AUTH", raising=False)
        settings = Settings(_env_file=None)  # type: ignore[call-arg]
        assert settings.enable_auth is False


class TestSettingsEnvValidation:
    """Verify GAIAOS_ENV validation."""

    @pytest.mark.parametrize("env_value", ["dev", "staging", "prod"])
    def test_gaiaos_env_accepts_valid_values(
        self,
        monkeypatch: pytest.MonkeyPatch,
        env_value: str,
    ) -> None:
        """GAIAOS_ENV accepts 'dev', 'staging', and 'prod'."""
        monkeypatch.setenv("GAIAOS_ENV", env_value)
        if env_value in ("staging", "prod"):
            monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
            monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        if env_value == "prod":
            monkeypatch.setenv("ENABLE_AUTH", "True")
        settings = Settings(_env_file=None)  # type: ignore[call-arg]
        assert settings.gaiaos_env == env_value

    def test_gaiaos_env_rejects_invalid_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """GAIAOS_ENV raises ValidationError for an undocumented value."""
        monkeypatch.setenv("GAIAOS_ENV", "production")  # not in the Literal
        with pytest.raises(ValidationError):
            Settings(_env_file=None)  # type: ignore[call-arg]


class TestDatabaseUrlRequirement:
    """Verify DATABASE_URL validation logic for non-dev environments."""

    def test_database_url_optional_in_dev(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """DATABASE_URL is not required when GAIAOS_ENV is 'dev'."""
        monkeypatch.setenv("GAIAOS_ENV", "dev")
        monkeypatch.delenv("DATABASE_URL", raising=False)
        settings = Settings(_env_file=None)  # type: ignore[call-arg]
        assert settings.database_url is None

    def test_database_url_required_in_staging(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Settings raises ValidationError when GAIAOS_ENV=staging and DATABASE_URL is absent."""
        monkeypatch.setenv("GAIAOS_ENV", "staging")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        monkeypatch.delenv("DATABASE_URL", raising=False)
        with pytest.raises(ValidationError, match="DATABASE_URL must be set"):
            Settings(_env_file=None)  # type: ignore[call-arg]

    def test_database_url_required_in_prod(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Settings raises ValidationError when GAIAOS_ENV=prod and DATABASE_URL is absent."""
        monkeypatch.setenv("GAIAOS_ENV", "prod")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("ENABLE_AUTH", "True")
        monkeypatch.delenv("DATABASE_URL", raising=False)
        with pytest.raises(ValidationError, match="DATABASE_URL must be set"):
            Settings(_env_file=None)  # type: ignore[call-arg]

    def test_database_url_accepted_in_staging(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Settings accepts a valid DATABASE_URL in staging."""
        monkeypatch.setenv("GAIAOS_ENV", "staging")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
        settings = Settings(_env_file=None)  # type: ignore[call-arg]
        assert settings.database_url == "postgresql://u:p@localhost:5432/db"

    def test_database_url_accepted_in_prod(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Settings accepts a valid DATABASE_URL in prod."""
        monkeypatch.setenv("GAIAOS_ENV", "prod")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("ENABLE_AUTH", "True")
        monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@prod-host:5432/db")
        settings = Settings(_env_file=None)  # type: ignore[call-arg]
        assert settings.database_url == "postgresql://u:p@prod-host:5432/db"


class TestEnableAuthRequirement:
    """Verify ENABLE_AUTH validation logic for production environments."""

    def test_enable_auth_required_in_prod(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Settings raises ValidationError when GAIAOS_ENV=prod and ENABLE_AUTH=False."""
        monkeypatch.setenv("GAIAOS_ENV", "prod")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@prod-host:5432/db")
        monkeypatch.setenv("ENABLE_AUTH", "False")
        with pytest.raises(ValidationError, match="ENABLE_AUTH must be True"):
            Settings(_env_file=None)  # type: ignore[call-arg]
