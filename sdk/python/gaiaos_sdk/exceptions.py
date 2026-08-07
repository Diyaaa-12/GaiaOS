"""Structured exception hierarchy for the GaiaOS Python SDK."""

from __future__ import annotations

from typing import Any


class GaiaSDKError(Exception):
    """Base exception for all GaiaOS SDK errors."""


class IncompatibleServerError(GaiaSDKError):
    """Raised when the server's API/app version is incompatible with this SDK."""


class GaiaAPIError(GaiaSDKError):
    """Exception raised when the GaiaOS server returns an HTTP error status."""

    def __init__(
        self,
        status_code: int,
        message: str,
        *,
        detail: Any = None,
        error_code: str | None = None,
    ) -> None:
        super().__init__(f"HTTP {status_code}: {message}")
        self.status_code = status_code
        self.message = message
        self.detail = detail
        self.error_code = error_code


class AuthenticationError(GaiaAPIError):
    """Raised on HTTP 401 Unauthorized responses."""


class PermissionDeniedError(GaiaAPIError):
    """Raised on HTTP 403 Forbidden responses."""


class NotFoundError(GaiaAPIError):
    """Raised on HTTP 404 Not Found responses."""


class RateLimitError(GaiaAPIError):
    """Raised on HTTP 429 Rate Limit Exceeded responses."""

    def __init__(
        self,
        status_code: int,
        message: str,
        *,
        detail: Any = None,
        error_code: str | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(status_code, message, detail=detail, error_code=error_code)
        self.retry_after = retry_after


class ServerError(GaiaAPIError):
    """Raised on HTTP 500+ Internal Server Error responses."""


def raise_for_status(status_code: int, response_json: Any = None, headers: Any = None) -> None:
    """Evaluate response status code and raise corresponding typed exception if 4xx/5xx."""
    if status_code < 400:
        return

    detail = None
    error_code = None
    message = f"Request failed with status code {status_code}"

    if isinstance(response_json, dict):
        detail = response_json.get("detail", response_json)
        error_code = response_json.get("error_code")
        if isinstance(detail, str):
            message = detail
        elif isinstance(detail, dict) and "message" in detail:
            message = str(detail["message"])

    if status_code == 401:
        raise AuthenticationError(status_code, message, detail=detail, error_code=error_code)
    if status_code == 403:
        raise PermissionDeniedError(status_code, message, detail=detail, error_code=error_code)
    if status_code == 404:
        raise NotFoundError(status_code, message, detail=detail, error_code=error_code)
    if status_code == 429:
        retry_hdr = headers.get("retry-after") if headers else None
        retry_after = float(retry_hdr) if retry_hdr and retry_hdr.isdigit() else None
        raise RateLimitError(
            status_code, message, detail=detail, error_code=error_code, retry_after=retry_after
        )
    if status_code >= 500:
        raise ServerError(status_code, message, detail=detail, error_code=error_code)

    raise GaiaAPIError(status_code, message, detail=detail, error_code=error_code)
