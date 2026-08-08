"""CLI configuration management and SDK client factory."""

from __future__ import annotations

import json
import os
from pathlib import Path

from gaiaos_sdk import GaiaClient
from pydantic import BaseModel


class CLIConfig(BaseModel):
    """Local configuration and stored credentials for GaiaOS CLI."""

    api_url: str = "http://localhost:8000"
    bearer_token: str | None = None
    api_key: str | None = None
    username: str | None = None


def get_config_dir() -> Path:
    """Return default configuration directory (~/.gaiaos)."""
    return Path.home() / ".gaiaos"


def get_config_path() -> Path:
    """Return path to config.json file (~/.gaiaos/config.json)."""
    return get_config_dir() / "config.json"


def load_config() -> CLIConfig:
    """Load CLI configuration from disk if available."""
    path = get_config_path()
    if not path.exists():
        return CLIConfig()

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return CLIConfig(**data)
    except Exception:
        pass
    return CLIConfig()


def save_config(config: CLIConfig) -> None:
    """Save CLI configuration to disk with platform-appropriate file security."""
    cfg_dir = get_config_dir()
    cfg_dir.mkdir(parents=True, exist_ok=True)

    path = get_config_path()
    content = config.model_dump_json(indent=2)
    path.write_text(content, encoding="utf-8")

    # Set 0o600 permissions on POSIX systems (Linux/macOS).
    # On Windows, POSIX 0o600 mode bits are not directly supported by standard filesystem ACLs,
    # so normal user profile isolation is used as best-effort per platform.
    if hasattr(os, "chmod") and os.name != "nt":
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass


def get_sdk_client(
    config: CLIConfig | None = None,
    *,
    api_url_override: str | None = None,
    api_key_override: str | None = None,
    token_override: str | None = None,
) -> GaiaClient:
    """Instantiate a GaiaClient instance using overrides, config, or environment variables."""
    cfg = config or load_config()

    base_url = (
        api_url_override
        or os.environ.get("GAIAOS_API_URL")
        or cfg.api_url
        or "http://localhost:8000"
    )
    api_key = api_key_override or os.environ.get("GAIAOS_API_KEY") or cfg.api_key
    bearer_token = token_override or os.environ.get("GAIAOS_BEARER_TOKEN") or cfg.bearer_token

    return GaiaClient(
        base_url=base_url,
        api_key=api_key,
        bearer_token=bearer_token,
    )
