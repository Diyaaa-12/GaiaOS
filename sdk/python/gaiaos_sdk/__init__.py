"""GaiaOS Python SDK — Typed, ergonomic client for the GaiaOS API.

Public API surface policy:
Only symbols exported directly from this module (or included in __all__)
are supported public interfaces. All modules under `gaiaos_sdk._generated`
are internal implementation details subject to change without major version bumps.
"""

from __future__ import annotations

import importlib.metadata

try:
    __version__ = importlib.metadata.version("gaiaos-sdk")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.0.0+dev"

from gaiaos_sdk.client import AsyncGaiaClient, GaiaClient
from gaiaos_sdk.exceptions import (
    AuthenticationError,
    GaiaAPIError,
    GaiaSDKError,
    IncompatibleServerError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    ServerError,
)
from gaiaos_sdk.streaming import StreamEvent

__all__ = [
    "__version__",
    "GaiaClient",
    "AsyncGaiaClient",
    "StreamEvent",
    "GaiaSDKError",
    "GaiaAPIError",
    "AuthenticationError",
    "PermissionDeniedError",
    "NotFoundError",
    "RateLimitError",
    "ServerError",
    "IncompatibleServerError",
]
