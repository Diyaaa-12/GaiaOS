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
    redis_url: str | None = Field(
        default=None,
        validation_alias="REDIS_URL",
        description="Redis connection URL (optional in dev; required for staging/prod).",
    )
    openaq_api_key: str | None = Field(
        default=None,
        validation_alias="OPENAQ_API_KEY",
        description="Optional API key for OpenAQ measurements provider.",
    )
    orchestrator_version: str = Field(
        default="1.0.0-dev",
        validation_alias="ORCHESTRATOR_VERSION",
        description="Active codebase version identifier.",
    )
    llm_model: str = Field(
        default="gpt-4o-mini",
        validation_alias="LLM_MODEL",
        description="Active LLM model identifier for completions.",
    )
    firms_api_key: str | None = Field(
        default=None,
        validation_alias="FIRMS_API_KEY",
        description="Optional API key for NASA FIRMS wildfire observations.",
    )
    agent_timeout: float = Field(
        default=30.0,
        validation_alias="AGENT_TIMEOUT",
        description="Timeout for individual agent executions in seconds.",
    )
    usgs_api_url: str = Field(
        default="https://earthquake.usgs.gov/fdsnws/event/1/query",
        validation_alias="USGS_API_URL",
        description="USGS Seismic API query URL.",
    )
    noaa_api_url: str = Field(
        default="https://api.tidesandcurrents.noaa.gov/api/prod/datagetter",
        validation_alias="NOAA_API_URL",
        description="NOAA Tides & Currents water temperature API URL.",
    )
    open_meteo_weather_url: str = Field(
        default="https://api.open-meteo.com/v1/forecast",
        validation_alias="OPEN_METEO_WEATHER_URL",
        description="Open-Meteo weather forecast API URL.",
    )
    open_meteo_geocoding_url: str = Field(
        default="https://geocoding-api.open-meteo.com/v1/search",
        validation_alias="OPEN_METEO_GEOCODING_URL",
        description="Open-Meteo location geocoding search URL.",
    )
    firms_api_url: str = Field(
        default="https://firms.modaps.eosdis.nasa.gov/api/area/csv",
        validation_alias="FIRMS_API_URL",
        description="NASA FIRMS wildfire CSV API URL.",
    )
    # ---------------------------------------------------------------------------
    # Literature & Embedding settings (Milestone 5)
    # ---------------------------------------------------------------------------
    embedding_api_key: str | None = Field(
        default=None,
        validation_alias="EMBEDDING_API_KEY",
        description="Optional API key for external embedding provider (OpenAI).",
    )
    embedding_model: str = Field(
        default="text-embedding-3-small",
        validation_alias="EMBEDDING_MODEL",
        description="Active model identifier for text embeddings.",
    )
    embedding_dimension: int = Field(
        default=1536,
        validation_alias="EMBEDDING_DIMENSION",
        description="Active dimension count for text embeddings.",
    )
    chunk_size: int = Field(
        default=500,
        validation_alias="CHUNK_SIZE",
        description="Standard character size for literature chunks.",
    )
    chunk_overlap: int = Field(
        default=50,
        validation_alias="CHUNK_OVERLAP",
        description="Character overlap for literature chunks.",
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
            "request — suitable for local development only."
        ),
    )
    # ---------------------------------------------------------------------------
    # Rate Limiting settings (Phase 3 Milestone 2)
    # ---------------------------------------------------------------------------
    enable_rate_limiting: bool = Field(
        default=False,
        validation_alias="ENABLE_RATE_LIMITING",
        description=(
            "Set to true to activate real Redis token-bucket rate limiting.  "
            "False (the default) keeps rate limiting in passthrough mode — "
            "suitable for local development and testing."
        ),
    )
    rate_limit_requests_per_minute: int = Field(
        default=60,
        validation_alias="RATE_LIMIT_REQUESTS_PER_MINUTE",
        description="Base rate limit in requests per minute.",
    )
    rate_limit_burst: int = Field(
        default=15,
        validation_alias="RATE_LIMIT_BURST",
        description="Maximum burst capacity (tokens) above steady rate.",
    )

    # ---------------------------------------------------------------------------
    # JWT Auth settings (Milestone 1)
    # ---------------------------------------------------------------------------
    jwt_secret_key: str | None = Field(
        default=None,
        validation_alias="JWT_SECRET_KEY",
        description="Secret key for JWT signing and validation. Required when ENABLE_AUTH is true.",
    )
    jwt_algorithm: str = Field(
        default="HS256",
        validation_alias="JWT_ALGORITHM",
        description="Algorithm for JWT signing.",
    )
    jwt_expiry_minutes: int = Field(
        default=60,
        validation_alias="JWT_EXPIRY_MINUTES",
        description="Access token validity in minutes.",
    )
    jwt_issuer: str = Field(
        default="gaiaos",
        validation_alias="JWT_ISSUER",
        description="Expected JWT issuer claim (iss).",
    )
    jwt_audience: str = Field(
        default="gaiaos-api",
        validation_alias="JWT_AUDIENCE",
        description="Expected JWT audience claim (aud).",
    )

    @model_validator(mode="after")
    def validate_production_security(self) -> Self:
        if self.gaiaos_env in ("staging", "prod") and not self.database_url:
            raise ValueError("DATABASE_URL must be set when GAIAOS_ENV is staging or prod")
        if self.gaiaos_env in ("staging", "prod") and not self.redis_url:
            raise ValueError("REDIS_URL must be set when GAIAOS_ENV is staging or prod")
        if self.gaiaos_env == "prod" and not self.enable_auth:
            raise ValueError("ENABLE_AUTH must be True when GAIAOS_ENV is prod")
        if self.gaiaos_env == "prod" and not self.enable_rate_limiting:
            raise ValueError("ENABLE_RATE_LIMITING must be True when GAIAOS_ENV is prod")
        if self.enable_auth or self.gaiaos_env in ("staging", "prod"):
            if not self.jwt_secret_key:
                raise ValueError(
                    "JWT_SECRET_KEY must be set when ENABLE_AUTH is True "
                    "or GAIAOS_ENV is staging/prod"
                )

            if len(self.jwt_secret_key) < 32:
                raise ValueError("JWT_SECRET_KEY must be at least 32 characters long")
        return self

    @property
    def asyncpg_url(self) -> str:
        """Return the database URL rewritten with the asyncpg driver."""
        if not self.database_url:
            raise RuntimeError("DATABASE_URL is not set.")

        url = self.database_url
        for prefix in ("postgresql://", "postgres://"):
            if url.startswith(prefix):
                return "postgresql+asyncpg://" + url[len(prefix) :]

        if url.startswith("postgresql+asyncpg://"):
            return url

        raise RuntimeError(
            f"DATABASE_URL must start with postgresql:// or postgres://; got: {url!r}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
