"""Single canonical source of truth for GaiaOS framework versioning."""

from __future__ import annotations

import importlib.metadata

try:
    __version__ = importlib.metadata.version("gaiaos")
except importlib.metadata.PackageNotFoundError:
    # Fallback for local git checkouts
    __version__ = "0.5.1"

GAIAOS_VERSION: str = __version__
