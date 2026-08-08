"""GaiaOS CLI Wizard — Command-line interface for GaiaOS."""

from __future__ import annotations

import importlib.metadata

try:
    __version__ = importlib.metadata.version("gaiaos-cli")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.0.0+dev"

__all__ = ["__version__"]
