"""Automated unit and regression tests for API Stability Contract enforcement."""

from __future__ import annotations

import copy
from typing import Any

from scripts.verify_api_stability import (
    check_spec_stability,
    resolve_schema,
    verify_api_stability,
)


def test_current_app_has_no_breaking_changes() -> None:
    """Live app regression test: verify FastAPI app has 0 breaking changes against baseline."""

    is_compatible, errors = verify_api_stability()
    assert is_compatible, f"Live app broke API stability contract: {errors}"
    assert len(errors) == 0


def create_minimal_baseline_spec() -> dict[str, Any]:
    """Helper to generate a clean, valid OpenAPI baseline spec dictionary."""
    return {
        "openapi": "3.1.0",
        "info": {"title": "GaiaOS API Test Baseline", "version": "1.0.0"},
        "components": {
            "schemas": {
                "UserSchema": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "email": {"type": "string"},
                    },
                    "required": ["id", "email"],
                }
            }
        },
        "paths": {
            "/api/v1/auth/me": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "User Profile",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/UserSchema"}
                                }
                            },
                        }
                    }
                }
            },
            "/api/v1/investigations": {
                "post": {
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "query": {"type": "string"},
                                        "domain_hint": {"type": "string"},
                                    },
                                    "required": ["query"],
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Investigation Created",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "investigation_id": {"type": "string"},
                                            "status": {"type": "string"},
                                        },
                                        "required": ["investigation_id", "status"],
                                    }
                                }
                            },
                        }
                    },
                }
            },
        },
    }


def test_detects_removed_endpoint() -> None:
    """Synthetic test: removing an endpoint under /api/v1/ must trigger breaking change."""
    baseline = create_minimal_baseline_spec()
    current = copy.deepcopy(baseline)
    del current["paths"]["/api/v1/auth/me"]

    is_compatible, errors = check_spec_stability(baseline, current)
    assert not is_compatible
    assert any("Endpoint removed" in e for e in errors)


def test_detects_removed_http_method() -> None:
    """Synthetic test: removing an HTTP method on a /api/v1/ route must trigger breaking change."""
    baseline = create_minimal_baseline_spec()
    current = copy.deepcopy(baseline)
    del current["paths"]["/api/v1/investigations"]["post"]

    is_compatible, errors = check_spec_stability(baseline, current)
    assert not is_compatible
    assert any("HTTP method 'POST' removed" in e for e in errors)


def test_detects_removed_response_status_code() -> None:
    """Synthetic test: removing a 200 response status code must trigger breaking change."""
    baseline = create_minimal_baseline_spec()
    current = copy.deepcopy(baseline)
    del current["paths"]["/api/v1/auth/me"]["get"]["responses"]["200"]

    is_compatible, errors = check_spec_stability(baseline, current)
    assert not is_compatible
    assert any("Response status code '200' removed" in e for e in errors)


def test_detects_removed_response_property() -> None:
    """Synthetic test: removing a property from a response schema must trigger breaking change."""
    baseline = create_minimal_baseline_spec()
    current = copy.deepcopy(baseline)
    del current["paths"]["/api/v1/investigations"]["post"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]["properties"]["status"]

    is_compatible, errors = check_spec_stability(baseline, current)
    assert not is_compatible
    assert any("Removed schema property 'status'" in e for e in errors)


def test_detects_request_body_property_became_required() -> None:
    """Synthetic test: optional request body property becoming required triggers failure."""

    baseline = create_minimal_baseline_spec()
    current = copy.deepcopy(baseline)
    current["paths"]["/api/v1/investigations"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]["required"].append("domain_hint")

    is_compatible, errors = check_spec_stability(baseline, current)
    assert not is_compatible
    assert any("became required in request schema" in e for e in errors)


def test_detects_incompatible_schema_type_change() -> None:
    """Synthetic test: changing property data type must trigger breaking change."""
    baseline = create_minimal_baseline_spec()
    current = copy.deepcopy(baseline)
    current["components"]["schemas"]["UserSchema"]["properties"]["id"]["type"] = "integer"

    is_compatible, errors = check_spec_stability(baseline, current)
    assert not is_compatible
    assert any("from 'string' to 'integer'" in e for e in errors)


def test_ref_and_allof_schema_resolution() -> None:
    """Synthetic test: verify $ref resolution and allOf property flattening."""
    components = {
        "schemas": {
            "Base": {"type": "object", "properties": {"base_field": {"type": "string"}}},
            "Child": {
                "allOf": [
                    {"$ref": "#/components/schemas/Base"},
                    {"type": "object", "properties": {"child_field": {"type": "number"}}},
                ]
            },
        }
    }

    resolved = resolve_schema({"$ref": "#/components/schemas/Child"}, components)
    assert "base_field" in resolved["properties"]
    assert "child_field" in resolved["properties"]


def test_v2_operation_level_exemption() -> None:
    """Synthetic test: breaking v1 change is exempt ONLY if equivalent v2 operation exists."""
    baseline = create_minimal_baseline_spec()
    current = copy.deepcopy(baseline)
    del current["paths"]["/api/v1/investigations"]["post"]

    # 1. Unrelated v2 route does NOT exempt v1 breaking change
    current["paths"]["/api/v2/unrelated"] = {"get": {"responses": {"200": {"description": "OK"}}}}
    is_compat_1, errs_1 = check_spec_stability(baseline, current)
    assert not is_compat_1
    assert any("POST /api/v1/investigations" in e for e in errs_1)

    # 2. Equivalent v2 operation (POST /api/v2/investigations) DOES exempt v1 operation
    current["paths"]["/api/v2/investigations"] = {
        "post": {"responses": {"200": {"description": "OK v2"}}}
    }
    is_compat_2, errs_2 = check_spec_stability(baseline, current)
    assert is_compat_2
    assert len(errs_2) == 0


def test_allows_non_breaking_additive_changes() -> None:
    """Synthetic test: adding new endpoints, optional params, or response fields is allowed."""

    baseline = create_minimal_baseline_spec()
    current = copy.deepcopy(baseline)

    # 1. Add new optional request parameter
    current["paths"]["/api/v1/auth/me"]["get"]["parameters"] = [
        {"name": "verbose", "in": "query", "required": False, "schema": {"type": "boolean"}}
    ]

    # 2. Add new response field
    current["components"]["schemas"]["UserSchema"]["properties"]["role"] = {"type": "string"}

    # 3. Add new endpoint
    current["paths"]["/api/v1/new-endpoint"] = {
        "get": {"responses": {"200": {"description": "New Endpoint"}}}
    }

    is_compatible, errors = check_spec_stability(baseline, current)
    assert is_compatible
    assert len(errors) == 0
