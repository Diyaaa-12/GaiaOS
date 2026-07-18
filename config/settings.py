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
    def require_database_url_outside_dev(self) -> Self:
        if self.gaiaos_env in ("staging", "prod") and not self.database_url:
            raise ValueError("DATABASE_URL must be set when GAIAOS_ENV is staging or prod")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
