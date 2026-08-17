"""Unit tests for SDK server version validation."""

import pytest
import respx
from gaiaos_sdk import GaiaClient, IncompatibleServerError, __version__
from httpx import Response


@respx.mock
def test_validate_server_matching_version() -> None:
    """Matching server version validates successfully."""
    respx.get("http://localhost:8000/api/v1/health/live").mock(
        return_value=Response(
            200, json={"status": "alive", "app_version": __version__, "schema_version": "1"}
        )
    )

    with GaiaClient(base_url="http://localhost:8000") as client:
        result = client.validate_server()
        assert result["status"] == "ok"
        assert result["server_version"] == __version__


@respx.mock
def test_validate_server_patch_no_warning() -> None:
    """Patch-only version difference raises no warnings."""
    patch_ver = f"{__version__.rsplit('.', 1)[0]}.99"
    respx.get("http://localhost:8000/api/v1/health/live").mock(
        return_value=Response(
            200, json={"status": "alive", "app_version": patch_ver, "schema_version": "1"}
        )
    )

    with GaiaClient(base_url="http://localhost:8000") as client:
        result = client.validate_server()
        assert result["status"] == "ok"
        assert result["server_version"] == patch_ver


@respx.mock
def test_validate_server_incompatible_major_version() -> None:
    """Incompatible major version raises IncompatibleServerError."""
    respx.get("http://localhost:8000/api/v1/health/live").mock(
        return_value=Response(
            200, json={"status": "alive", "app_version": "2.0.0", "schema_version": "1"}
        )
    )

    with GaiaClient(base_url="http://localhost:8000") as client:
        with pytest.raises(IncompatibleServerError) as exc_info:
            client.validate_server()
        assert "major version incompatible" in str(exc_info.value)


@respx.mock
def test_validate_server_minor_warning() -> None:
    """Minor version mismatch issues UserWarning."""
    respx.get("http://localhost:8000/api/v1/health/live").mock(
        return_value=Response(
            200, json={"status": "alive", "app_version": "1.1.0", "schema_version": "1"}
        )
    )

    with GaiaClient(base_url="http://localhost:8000") as client:
        with pytest.warns(UserWarning, match="minor release differs"):
            client.validate_server()
