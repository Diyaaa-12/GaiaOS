"""GaiaOS API Stability & Breaking-Change Detector.

Compares an OpenAPI specification baseline (docs/api/openapi/openapi.json)
against a current OpenAPI specification (app.openapi()) to enforce the v1.0
Public API Stability Contract defined in docs/api/STABILITY.md.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# Ensure repository root is in sys.path when invoked directly
_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))


def resolve_schema(
    schema: dict[str, Any], components: dict[str, Any], depth: int = 0
) -> dict[str, Any]:
    """Recursively resolve $ref pointers and flatten allOf compositions conservatively.

    Preserves oneOf/anyOf structures without blind flattening to retain exact semantics.
    """
    if depth > 20:
        return schema

    if not isinstance(schema, dict):
        return {}

    # 1. Resolve $ref
    if "$ref" in schema:
        ref_path = schema["$ref"].split("/")
        if len(ref_path) >= 4 and ref_path[1] == "components" and ref_path[2] == "schemas":
            schema_name = ref_path[3]
            target_schema = components.get("schemas", {}).get(schema_name, {})
            return resolve_schema(target_schema, components, depth + 1)

    resolved = dict(schema)

    # 2. Flatten allOf conservatively
    if "allOf" in schema and isinstance(schema["allOf"], list):
        merged_props: dict[str, Any] = {}
        merged_req: set[str] = set()
        schema_type = resolved.get("type", "object")

        for sub_s in schema["allOf"]:
            sub_resolved = resolve_schema(sub_s, components, depth + 1)
            if "properties" in sub_resolved:
                merged_props.update(sub_resolved["properties"])
            if "required" in sub_resolved and isinstance(sub_resolved["required"], list):
                merged_req.update(sub_resolved["required"])
            if "type" in sub_resolved:
                schema_type = sub_resolved["type"]

        resolved["type"] = schema_type
        existing_props = resolved.get("properties", {})
        existing_props.update(merged_props)
        resolved["properties"] = existing_props

        existing_req = set(resolved.get("required", []))
        existing_req.update(merged_req)
        resolved["required"] = sorted(existing_req)

    return resolved


def extract_schema_properties(
    schema: dict[str, Any], components: dict[str, Any]
) -> tuple[dict[str, Any], set[str]]:
    """Extract effective properties and required fields from a schema dictionary."""
    resolved = resolve_schema(schema, components)
    props = resolved.get("properties", {})
    req = set(resolved.get("required", []))
    return props, req


def check_schema_compatibility(
    base_schema: dict[str, Any],
    curr_schema: dict[str, Any],
    base_components: dict[str, Any],
    curr_components: dict[str, Any],
    location_prefix: str,
) -> list[str]:
    """Check two schemas for breaking structural changes."""
    errors: list[str] = []

    base_props, base_req = extract_schema_properties(base_schema, base_components)
    curr_props, curr_req = extract_schema_properties(curr_schema, curr_components)

    for p_name, base_p in base_props.items():
        if p_name not in curr_props:
            errors.append(f"{location_prefix}: Removed schema property '{p_name}'.")
            continue

        curr_p = curr_props[p_name]
        base_p_resolved = resolve_schema(base_p, base_components)
        curr_p_resolved = resolve_schema(curr_p, curr_components)

        base_type = base_p_resolved.get("type")
        curr_type = curr_p_resolved.get("type")

        if base_type and curr_type and base_type != curr_type:
            errors.append(
                f"{location_prefix}: Changed type of property '{p_name}' "
                f"from '{base_type}' to '{curr_type}'."
            )

        # Check optional -> required change in request
        if "request" in location_prefix.lower():
            if p_name not in base_req and p_name in curr_req:
                errors.append(
                    f"{location_prefix}: Optional property '{p_name}' "
                    "became required in request schema."
                )

    return errors


def check_spec_stability(
    baseline_spec: dict[str, Any], current_spec: dict[str, Any]
) -> tuple[bool, list[str]]:
    """Evaluate current OpenAPI spec against baseline spec for breaking changes.

    Returns:
        (is_compatible, list_of_breaking_change_errors)
    """
    errors: list[str] = []

    base_paths = baseline_spec.get("paths", {})
    curr_paths = current_spec.get("paths", {})

    base_components = baseline_spec.get("components", {})
    curr_components = current_spec.get("components", {})

    for path, base_item in base_paths.items():
        # Root landing page '/' is excluded from stability contract
        if not path.startswith("/api/v1/"):
            continue

        for method, base_op in base_item.items():
            if method in ("parameters", "summary", "description"):
                continue

            method_upper = method.upper()
            op_label = f"{method_upper} {path}"

            # v2 Exemption Check: Exact operation match under /api/v2/
            v2_path = path.replace("/api/v1/", "/api/v2/")
            v2_has_operation = (
                v2_path in curr_paths
                and isinstance(curr_paths[v2_path], dict)
                and method in curr_paths[v2_path]
            )

            # 1. Path or Method Removal
            if path not in curr_paths:
                if not v2_has_operation:
                    errors.append(
                        f"BREAKING CHANGE [{op_label}]: Endpoint removed "
                        "without equivalent /v2 endpoint."
                    )
                continue

            curr_item = curr_paths[path]
            if not isinstance(curr_item, dict) or method not in curr_item:
                if not v2_has_operation:
                    errors.append(
                        f"BREAKING CHANGE [{op_label}]: HTTP method '{method_upper}' "
                        "removed without equivalent /v2 operation."
                    )
                continue

            # If v2 operation exists, this v1 operation is exempt from further breaking checks
            if v2_has_operation:
                continue

            curr_op = curr_item[method]

            # 2. Check Request Parameters
            base_params = {
                (p.get("name"), p.get("in")): p
                for p in base_op.get("parameters", [])
                if isinstance(p, dict)
            }
            curr_params = {
                (p.get("name"), p.get("in")): p
                for p in curr_op.get("parameters", [])
                if isinstance(p, dict)
            }

            for (p_name, p_in), base_p in base_params.items():
                if (p_name, p_in) not in curr_params:
                    errors.append(
                        f"BREAKING CHANGE [{op_label}]: Removed parameter '{p_name}' in '{p_in}'."
                    )
                    continue

                curr_p = curr_params[(p_name, p_in)]
                if not base_p.get("required", False) and curr_p.get("required", False):
                    errors.append(
                        f"BREAKING CHANGE [{op_label}]: Parameter '{p_name}' in '{p_in}' "
                        "changed from optional to required."
                    )

            # 3. Check Request Body
            base_req_body = base_op.get("requestBody", {})
            curr_req_body = curr_op.get("requestBody", {})

            if base_req_body and not curr_req_body:
                errors.append(f"BREAKING CHANGE [{op_label}]: Request body removed.")
            elif base_req_body and curr_req_body:
                base_content = base_req_body.get("content", {})
                curr_content = curr_req_body.get("content", {})

                for c_type, base_media in base_content.items():
                    if c_type not in curr_content:
                        errors.append(
                            f"BREAKING CHANGE [{op_label}]: Request body media type '{c_type}' "
                            "removed."
                        )
                        continue

                    curr_media = curr_content[c_type]
                    base_s = base_media.get("schema", {})
                    curr_s = curr_media.get("schema", {})

                    schema_errs = check_schema_compatibility(
                        base_s,
                        curr_s,
                        base_components,
                        curr_components,
                        f"BREAKING CHANGE [{op_label}] (Request Body {c_type})",
                    )
                    errors.extend(schema_errs)

            # 4. Check Response Contract
            base_responses = base_op.get("responses", {})
            curr_responses = curr_op.get("responses", {})

            for status_code, base_resp in base_responses.items():
                if status_code not in curr_responses:
                    errors.append(
                        f"BREAKING CHANGE [{op_label}]: Response status code '{status_code}' "
                        "removed."
                    )
                    continue

                curr_resp = curr_responses[status_code]
                base_r_content = base_resp.get("content", {})
                curr_r_content = curr_resp.get("content", {})

                for c_type, base_r_media in base_r_content.items():
                    if c_type not in curr_r_content:
                        errors.append(
                            f"BREAKING CHANGE [{op_label}]: Response content media type '{c_type}' "
                            f"for status '{status_code}' removed."
                        )
                        continue


                    curr_r_media = curr_r_content[c_type]
                    base_r_s = base_r_media.get("schema", {})
                    curr_r_s = curr_r_media.get("schema", {})

                    resp_schema_errs = check_schema_compatibility(
                        base_r_s,
                        curr_r_s,
                        base_components,
                        curr_components,
                        f"BREAKING CHANGE [{op_label}] (Response {status_code} {c_type})",
                    )
                    errors.extend(resp_schema_errs)

    is_compatible = len(errors) == 0
    return is_compatible, errors


def verify_api_stability(
    baseline_path: Path | None = None,
) -> tuple[bool, list[str]]:
    """Load baseline OpenAPI JSON and verify current FastAPI app.openapi() for stability."""
    if baseline_path is None:
        repo_root = Path(__file__).resolve().parent.parent
        baseline_path = repo_root / "docs" / "api" / "openapi" / "openapi.json"

    if not baseline_path.exists():
        return False, [f"Baseline OpenAPI spec not found at {baseline_path}"]

    baseline_spec = json.loads(baseline_path.read_text(encoding="utf-8"))

    from app.main import app

    current_spec = app.openapi()

    return check_spec_stability(baseline_spec, current_spec)


def main() -> int:
    """CLI entrypoint for API stability check."""
    is_compatible, errors = verify_api_stability()

    if not is_compatible:
        print("[ERROR] API Stability Contract Violation Detected:\n", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print("[OK] API Stability Contract check passed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
