from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from orchestrator.__version__ import GAIAOS_VERSION


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
    read_replica_database_url: str | None = Field(
        default=None,
        validation_alias="READ_REPLICA_DATABASE_URL",
        description="Optional PostgreSQL connection URL for read-replica queries.",
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
        default=GAIAOS_VERSION,
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
    enable_agent_collaboration: bool = Field(
        default=False,
        validation_alias="ENABLE_AGENT_COLLABORATION",
        description="Feature flag for Phase 5 Milestone 4 Multi-Agent Collaboration Protocol.",
    )
    min_cross_domain_evidence: int = Field(
        default=2,
        validation_alias="MIN_CROSS_DOMAIN_EVIDENCE",
        description="Minimum distinct domain sources required for a cross_domain_pattern claim.",
    )
    plugins_enabled: bool = Field(
        default=True,
        validation_alias="PLUGINS_ENABLED",
        description="Feature flag to enable dynamic discovery of agent plugins at worker startup.",
    )
    strict_plugin_validation: bool = Field(
        default=False,
        validation_alias="STRICT_PLUGIN_VALIDATION",
        description=(
            "If True, any plugin validation error aborts worker boot; "
            "if False, disables faulty plugin with loud error."
        ),
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
        description="Open-Meteo geocoding search API URL.",
    )
    causal_chain_search_radius_meters: float = Field(
        default=50000.0,
        validation_alias="CAUSAL_CHAIN_SEARCH_RADIUS_METERS",
        description="Default search radius in meters for causal chain spatial proximity matching.",
    )
    enable_usgs_ingestion: bool = Field(
        default=True,
        validation_alias="ENABLE_USGS_INGESTION",
        description="Enable automated USGS seismic event ingestion pipeline.",
    )
    enable_noaa_ingestion: bool = Field(
        default=True,
        validation_alias="ENABLE_NOAA_INGESTION",
        description="Enable automated NOAA ocean event ingestion pipeline.",
    )
    enable_copernicus_ingestion: bool = Field(
        default=True,
        validation_alias="ENABLE_COPERNICUS_INGESTION",
        description="Enable automated Copernicus Sentinel wildfire metadata ingestion pipeline.",
    )
    enable_era5_ingestion: bool = Field(
        default=True,
        validation_alias="ENABLE_ERA5_INGESTION",
        description="Enable automated ERA5 atmospheric reanalysis baseline ingestion pipeline.",
    )
    enable_gdelt_ingestion: bool = Field(
        default=True,
        validation_alias="ENABLE_GDELT_INGESTION",
        description="Enable automated GDELT socio-political hazard context ingestion pipeline.",
    )
    ingestion_poll_interval_hours: int = Field(
        default=1,
        validation_alias="INGESTION_POLL_INTERVAL_HOURS",
        description="Interval in hours between scheduled hazard event ingestion runs.",
    )
    firms_api_url: str = Field(
        default="https://firms.modaps.eosdis.nasa.gov/api/area/csv",
        validation_alias="FIRMS_API_URL",
        description="NASA FIRMS wildfire CSV API URL.",
    )
    copernicus_api_url: str = Field(
        default="https://catalogue.dataspace.copernicus.eu/odata/v1",
        validation_alias="COPERNICUS_API_URL",
        description="Copernicus Data Space OData API URL.",
    )
    era5_api_url: str = Field(
        default="https://archive-api.open-meteo.com/v1/archive",
        validation_alias="ERA5_API_URL",
        description="ERA5 atmospheric reanalysis API URL (via Open-Meteo archive service).",
    )
    gdelt_api_url: str = Field(
        default="https://api.gdeltproject.org/api/v2/doc/doc",
        validation_alias="GDELT_API_URL",
        description="GDELT DOC 2.0 API endpoint URL.",
    )
    gdelt_max_records_per_run: int = Field(
        default=250,
        validation_alias="GDELT_MAX_RECORDS_PER_RUN",
        description="Maximum number of GDELT event records ingested per scheduled run.",
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
    # Backup & Disaster Recovery settings (Phase 4 Milestone 6)
    # ---------------------------------------------------------------------------
    backup_cron: str = Field(
        default="0 2 * * *",
        validation_alias="BACKUP_CRON",
        description="Cron expression for automated database backup schedule.",
    )
    restore_drill_cron: str = Field(
        default="0 4 1 * *",
        validation_alias="RESTORE_DRILL_CRON",
        description="Cron expression for automated database restore drill schedule.",
    )
    backup_retention_days: int = Field(
        default=30,
        validation_alias="BACKUP_RETENTION_DAYS",
        description="Retention period in days before expired backups are purged.",
    )
    backup_storage_path: str = Field(
        default="./backups",
        validation_alias="BACKUP_STORAGE_PATH",
        description="Local or S3-compatible directory path for database backup files.",
    )
    # ---------------------------------------------------------------------------
    # Public Research API & Dataset Publishing settings (Phase 5 Milestone 9)
    # ---------------------------------------------------------------------------
    public_research_api_enabled: bool = Field(
        default=True,
        validation_alias="PUBLIC_RESEARCH_API_ENABLED",
        description="Feature flag enabling read-only public research API endpoints.",
    )
    dataset_export_enabled: bool = Field(
        default=True,
        validation_alias="DATASET_EXPORT_ENABLED",
        description="Feature flag enabling monthly public dataset export background job.",
    )
    dataset_export_dir: str = Field(
        default="./data/exports",
        validation_alias="DATASET_EXPORT_DIR",
        description="Directory path for versioned public dataset export archives.",
    )
    research_api_rate_limit: str = Field(
        default="60/minute",
        validation_alias="RESEARCH_API_RATE_LIMIT",
        description="Rate limit string for public research API endpoints.",
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
    # Task Queue & Checkpoint settings (Phase 3 Milestones 3 & 4)
    # ---------------------------------------------------------------------------
    use_queued_execution: bool = Field(
        default=True,
        validation_alias="USE_QUEUED_EXECUTION",
        description=(
            "Set to true to enqueue investigation jobs via RQ worker queue. "
            "Set to false for legacy BackgroundTasks fallback execution."
        ),
    )
    job_timeout_seconds: int = Field(
        default=600,
        validation_alias="JOB_TIMEOUT_SECONDS",
        description="Maximum execution time allowed for an investigation job in seconds.",
    )
    job_max_retries: int = Field(
        default=2,
        validation_alias="JOB_MAX_RETRIES",
        description="Maximum number of retry attempts for an investigation job upon worker crash.",
    )
    checkpoint_ttl_safety_factor: float = Field(
        default=2.0,
        validation_alias="CHECKPOINT_TTL_SAFETY_FACTOR",
        description="Safety factor multiplier for checkpoint TTL calculation.",
    )
    checkpoint_ttl_seconds_override: int | None = Field(
        default=None,
        validation_alias="CHECKPOINT_TTL_SECONDS",
        description=(
            "Explicit override for checkpoint TTL in seconds. If unset, calculated automatically."
        ),
    )
    # ---------------------------------------------------------------------------
    # Worker Scaling & Resource Configuration (Phase 4 Milestone 7)
    # ---------------------------------------------------------------------------
    worker_pool_size: int = Field(
        default=2,
        validation_alias="WORKER_POOL_SIZE",
        description="Configured worker process pool size (minimum bound for scaling).",
    )
    worker_concurrency_per_process: int = Field(
        default=1,
        validation_alias="WORKER_CONCURRENCY_PER_PROCESS",
        description="Concurrency threads per worker process instance.",
    )
    worker_target_max_wait_s: float = Field(
        default=60.0,
        validation_alias="WORKER_TARGET_MAX_WAIT_S",
        description="Target maximum queue wait SLA in seconds for scaling recommendations.",
    )
    app_cpu_limit: str = Field(
        default="1.0",
        validation_alias="APP_CPU_LIMIT",
        description="Configurable CPU limit for main API app container.",
    )
    app_memory_limit: str = Field(
        default="512M",
        validation_alias="APP_MEMORY_LIMIT",
        description="Configurable memory limit for main API app container.",
    )
    worker_cpu_limit: str = Field(
        default="1.0",
        validation_alias="WORKER_CPU_LIMIT",
        description="Configurable CPU limit for background worker container.",
    )
    worker_memory_limit: str = Field(
        default="512M",
        validation_alias="WORKER_MEMORY_LIMIT",
        description="Configurable memory limit for background worker container.",
    )
    scheduler_cpu_limit: str = Field(
        default="0.5",
        validation_alias="SCHEDULER_CPU_LIMIT",
        description="Configurable CPU limit for RQ scheduler container.",
    )
    scheduler_memory_limit: str = Field(
        default="256M",
        validation_alias="SCHEDULER_MEMORY_LIMIT",
        description="Configurable memory limit for RQ scheduler container.",
    )
    scaling_summary_interval_s: int = Field(
        default=300,
        validation_alias="SCALING_SUMMARY_INTERVAL_S",
        description="Interval in seconds for periodic worker scaling log summary.",
    )
    # ---------------------------------------------------------------------------
    # Critic Replan Loop settings (Phase 3 Milestone 6)
    # ---------------------------------------------------------------------------
    enable_replan_loop: bool = Field(
        default=False,
        validation_alias="ENABLE_REPLAN_LOOP",
        description=(
            "Set to true to activate bounded critic replan loop on high-severity critic flags. "
            "False (the default) keeps replanning in passthrough mode for A/B evaluation."
        ),
    )
    # ---------------------------------------------------------------------------
    # Resilience Layer settings (Phase 6 Milestone 1)
    # ---------------------------------------------------------------------------
    resilience_bypass: bool = Field(
        default=False,
        validation_alias="RESILIENCE_BYPASS",
        description=(
            "Bypass the resilience layer and revert to bare Phase 5 tool-call behaviour. "
            "Dev/test only — never enable in staging or prod."
        ),
    )
    circuit_failure_threshold: int = Field(
        default=5,
        validation_alias="CIRCUIT_FAILURE_THRESHOLD",
        description=(
            "Number of consecutive failures before a source's circuit breaker opens. "
            "Lower values open faster (more protective); higher values tolerate transient blips."
        ),
    )
    circuit_half_open_timeout_s: int = Field(
        default=60,
        validation_alias="CIRCUIT_HALF_OPEN_TIMEOUT_S",
        description=(
            "Seconds after circuit opens before a probe attempt is allowed (half-open window). "
            "After this window the circuit transitions from open to half-open."
        ),
    )


    @property
    def checkpoint_ttl_seconds(self) -> int:
        """Return the TTL for LangGraph checkpoint keys in Redis in seconds.

        If CHECKPOINT_TTL_SECONDS is explicitly configured, returns that value.
        Otherwise, computes default TTL from job timeout, max retries, and safety margin:
            job_timeout_seconds * (job_max_retries + 1) * safety_factor
        """
        if self.checkpoint_ttl_seconds_override is not None:
            return self.checkpoint_ttl_seconds_override
        worst_case_duration = self.job_timeout_seconds * (self.job_max_retries + 1)
        return int(worst_case_duration * self.checkpoint_ttl_safety_factor)

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
    app_base_url: str = Field(
        default="http://localhost:8000",
        validation_alias="APP_BASE_URL",
        description="Configured base URL for application link generation.",
    )
    password_reset_expiry_minutes: int = Field(
        default=15,
        validation_alias="PASSWORD_RESET_EXPIRY_MINUTES",
        description="Password reset token validity window in minutes.",
    )
    password_reset_rate_limit_requests: int = Field(
        default=3,
        validation_alias="PASSWORD_RESET_RATE_LIMIT_REQUESTS",
        description="Maximum allowed password reset requests per time window.",
    )
    password_reset_rate_limit_window_seconds: int = Field(
        default=900,
        validation_alias="PASSWORD_RESET_RATE_LIMIT_WINDOW_SECONDS",
        description="Rate limit time window in seconds for password reset endpoint.",
    )
    alerting_enabled: bool = Field(
        default=True,
        validation_alias="ALERTING_ENABLED",
        description="Global feature flag for automated production alerting.",
    )
    alert_evaluation_interval_minutes: int = Field(
        default=5,
        validation_alias="ALERT_EVALUATION_INTERVAL_MINUTES",
        description="Evaluation frequency in minutes for background alert worker job.",
    )
    alert_webhook_url: str | None = Field(
        default=None,
        validation_alias="ALERT_WEBHOOK_URL",
        description="Target Webhook URL for alert notifications (secret, never logged).",
    )
    alert_flapping_min_cycles: int = Field(
        default=1,
        validation_alias="ALERT_FLAPPING_MIN_CYCLES",
        description="Global default minimum consecutive firing cycles before notifying.",
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

    @property
    def read_asyncpg_url(self) -> str | None:
        """Return the read-replica database URL rewritten with the asyncpg driver."""
        if not self.read_replica_database_url:
            return None

        url = self.read_replica_database_url
        for prefix in ("postgresql://", "postgres://"):
            if url.startswith(prefix):
                return "postgresql+asyncpg://" + url[len(prefix) :]

        if url.startswith("postgresql+asyncpg://"):
            return url

        raise RuntimeError(
            f"READ_REPLICA_DATABASE_URL must start with postgresql:// or postgres://; got: {url!r}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
