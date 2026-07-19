from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    gaiaos_env: Literal["dev", "staging", "prod"] = Field(
        default="dev",
        validation_alias="GAIAOS_ENV",
    )
    log_level: str = Field(default="DEBUG", validation_alias="LOG_LEVEL")
    database_url: str | None = Field(
        default=None,
        validation_alias="DATABASE_URL",
        description="PostgreSQL connection URL (optional in dev; required for staging/prod).",
    )
    # ---------------------------------------------------------------------------
    # Gateway settings (Milestone 7)
    # ---------------------------------------------------------------------------
    enable_auth: bool = Field(
        default=False,
        validation_alias="ENABLE_AUTH",
        description=(
            "Set to true to activate real authentication enforcement.  "
            "False (the default) keeps the AuthStub active, which allows every "
            "request — suitable for local development only.  "
            "TODO(M_AUTH): Remove this flag once auth is mandatory in all envs."
        ),
    )

    @model_validator(mode="after")
    def validate_production_security(self) -> Self:
        if self.gaiaos_env in ("staging", "prod") and not self.database_url:
            raise ValueError("DATABASE_URL must be set when GAIAOS_ENV is staging or prod")
        if self.gaiaos_env == "prod" and not self.enable_auth:
            raise ValueError("ENABLE_AUTH must be True when GAIAOS_ENV is prod")
        return self

    @property
    def asyncpg_url(self) -> str:
        """Return the database URL rewritten with the asyncpg driver."""
        if not self.database_url:
            raise RuntimeError("DATABASE_URL is not set.")

        url = self.database_url
        for prefix in ("postgresql://", "postgres://"):
            if url.startswith(prefix):
                return "postgresql+asyncpg://" + url[len(prefix):]

        if url.startswith("postgresql+asyncpg://"):
            return url

        raise RuntimeError(
            f"DATABASE_URL must start with postgresql:// or postgres://; got: {url!r}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
