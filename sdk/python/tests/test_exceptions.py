"""Unit tests for SDK exception mapping and hierarchy."""

import pytest
from gaiaos_sdk.exceptions import (
    AuthenticationError,
    GaiaAPIError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    ServerError,
    raise_for_status,
)


def test_raise_for_status_200_ok() -> None:
    """Status codes < 400 should not raise any exception."""
    raise_for_status(200, {"status": "ok"})
    raise_for_status(201, {"id": "123"})


def test_raise_for_status_401_auth_error() -> None:
    """Status 401 raises AuthenticationError."""
    with pytest.raises(AuthenticationError) as exc_info:
        raise_for_status(401, {"detail": "Invalid credentials", "error_code": "invalid_auth"})
    assert exc_info.value.status_code == 401
    assert "Invalid credentials" in str(exc_info.value)
    assert exc_info.value.error_code == "invalid_auth"


def test_raise_for_status_403_permission_error() -> None:
    """Status 403 raises PermissionDeniedError."""
    with pytest.raises(PermissionDeniedError) as exc_info:
        raise_for_status(403, {"detail": "Access forbidden"})
    assert exc_info.value.status_code == 403


def test_raise_for_status_404_not_found() -> None:
    """Status 404 raises NotFoundError."""
    with pytest.raises(NotFoundError) as exc_info:
        raise_for_status(404, {"detail": "Investigation not found"})
    assert exc_info.value.status_code == 404


def test_raise_for_status_429_rate_limit() -> None:
    """Status 429 raises RateLimitError with retry_after parsing."""
    with pytest.raises(RateLimitError) as exc_info:
        raise_for_status(429, {"detail": "Too many requests"}, headers={"retry-after": "30"})
    assert exc_info.value.status_code == 429
    assert exc_info.value.retry_after == 30.0


def test_raise_for_status_500_server_error() -> None:
    """Status 500 raises ServerError."""
    with pytest.raises(ServerError) as exc_info:
        raise_for_status(500, {"detail": "Internal error"})
    assert exc_info.value.status_code == 500


def test_raise_for_status_generic_4xx() -> None:
    """Unhandled 4xx status code raises generic GaiaAPIError."""
    with pytest.raises(GaiaAPIError) as exc_info:
        raise_for_status(418, {"detail": "I'm a teapot"})
    assert exc_info.value.status_code == 418
