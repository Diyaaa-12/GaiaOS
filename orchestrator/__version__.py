"""Single canonical source of truth for GaiaOS framework versioning."""

from __future__ import annotations

import importlib.metadata
import tomllib
from pathlib import Path


def _get_version() -> str:
    """Resolve the canonical GaiaOS framework version.

    Resolution order:
    1. importlib.metadata.version("gaiaos")
    2. pyproject.toml project.version via tomllib
    3. RuntimeError if neither is available
    """
    try:
        return importlib.metadata.version("gaiaos")
    except importlib.metadata.PackageNotFoundError:
        pass

    pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
    if pyproject_path.exists():
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
        version = data.get("project", {}).get("version")
        if version:
            return version

    raise RuntimeError(
        "Unable to determine GaiaOS version: package 'gaiaos' is not installed "
        "and pyproject.toml was not found or contains no project.version."
    )


__version__: str = _get_version()
GAIAOS_VERSION: str = __version__

