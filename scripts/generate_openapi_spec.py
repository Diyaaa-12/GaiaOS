"""Generate deterministic OpenAPI specification for GaiaOS public API."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# Ensure repository root is in sys.path
_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from app.main import app  # noqa: E402


def generate_openapi_spec() -> dict[str, Any]:
    """Retrieve the OpenAPI schema dictionary from the FastAPI application.

    Returns:
        A dictionary representing the OpenAPI 3.1.0 specification.
    """
    return app.openapi()


def write_openapi_spec(output_path: Path | None = None) -> Path:
    """Generate and write the deterministic OpenAPI specification to disk.

    Args:
        output_path: Optional explicit output path. Defaults to
            `docs/api/openapi/openapi.json` relative to repository root.

    Returns:
        Path object of the written OpenAPI JSON file.
    """
    if output_path is None:
        repo_root = Path(__file__).resolve().parent.parent
        output_path = repo_root / "docs" / "api" / "openapi" / "openapi.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    spec = generate_openapi_spec()
    content = json.dumps(spec, indent=2, sort_keys=True, ensure_ascii=False) + "\n"

    output_path.write_text(content, encoding="utf-8")
    return output_path


def main() -> None:
    """CLI entrypoint for generating the OpenAPI specification."""
    written_path = write_openapi_spec()
    print(f"Successfully generated OpenAPI specification at {written_path}")


if __name__ == "__main__":
    main()
