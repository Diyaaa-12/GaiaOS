"""Automated tests for OpenAPI specification generation, schema security, and idempotency."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.generate_openapi_spec import generate_openapi_spec, write_openapi_spec


def test_openapi_spec_generation_and_validity() -> None:
    """Verify generate_openapi_spec returns a valid OpenAPI 3.x specification dictionary."""
    spec = generate_openapi_spec()

    assert isinstance(spec, dict)
    assert spec.get("openapi", "").startswith("3.")
    assert isinstance(spec.get("info"), dict)
    assert spec["info"].get("title")
    assert spec.get("paths")


def test_openapi_spec_write_idempotency(tmp_path: Path) -> None:
    """Verify write_openapi_spec produces byte-for-byte identical output.

    Tests that running the write function twice generates identical bytes.
    """
    test_file_1 = tmp_path / "subdir_a" / "openapi.json"
    test_file_2 = tmp_path / "subdir_b" / "openapi.json"

    out_path_1 = write_openapi_spec(test_file_1)
    out_path_2 = write_openapi_spec(test_file_2)

    assert out_path_1.exists()
    assert out_path_2.exists()

    content_1 = out_path_1.read_bytes()
    content_2 = out_path_2.read_bytes()

    assert content_1 == content_2
    assert content_1

    # Confirm it parses as valid JSON
    parsed = json.loads(content_1.decode("utf-8"))
    assert parsed.get("openapi", "").startswith("3.")
    assert parsed.get("paths")


def test_openapi_spec_internal_route_excluded() -> None:
    """Verify internal infrastructure routes (/internal/*) are excluded from OpenAPI schema."""
    spec = generate_openapi_spec()
    paths = spec.get("paths", {})

    assert "/internal/smoke-job" not in paths
    for path_str in paths:
        assert not path_str.startswith("/internal")


def test_openapi_spec_public_routes_present() -> None:
    """Verify representative audited public endpoints are present in the OpenAPI schema."""
    spec = generate_openapi_spec()
    paths = spec.get("paths", {})

    representative_public_routes = [
        "/",
        "/api/v1/ping",
        "/api/v1/investigations",
        "/api/v1/admin/metrics",
    ]

    for route in representative_public_routes:
        assert route in paths, f"Expected public route '{route}' missing from OpenAPI spec paths"
