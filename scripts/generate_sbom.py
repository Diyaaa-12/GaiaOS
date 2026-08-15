"""GaiaOS CycloneDX v1.6 Software Bill of Materials (SBOM) Generator.

Parses locked dependencies from requirements/base.lock and formats a valid,
deterministic CycloneDX v1.6 JSON document for release artifacts.
Uses standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import uuid
from pathlib import Path
from typing import Any

_repo_root = Path(__file__).resolve().parent.parent


def get_project_version(pyproject_path: Path | None = None) -> str:
    """Extract project version from pyproject.toml without runtime dependencies."""
    if pyproject_path is None:
        pyproject_path = _repo_root / "pyproject.toml"

    if not pyproject_path.exists():
        raise FileNotFoundError(f"pyproject.toml not found at {pyproject_path}")

    content = pyproject_path.read_text(encoding="utf-8")
    match = re.search(r'version\s*=\s*"([^"]+)"', content)
    if match:
        return match.group(1)

    raise ValueError(f"Could not find version field in {pyproject_path}")



def parse_lockfile_packages(lockfile_path: Path) -> list[dict[str, str]]:
    """Parse locked Python package names and versions from a pip lockfile."""
    if not lockfile_path.exists():
        raise FileNotFoundError(f"Lockfile not found at {lockfile_path}")

    packages: list[dict[str, str]] = []
    content = lockfile_path.read_text(encoding="utf-8")

    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue

        # Match package==version syntax (e.g. fastapi==0.110.0)
        if "==" in line:
            parts = line.split("==")
            pkg_name = parts[0].strip().lower()
            pkg_version = parts[1].split(";")[0].strip()
            packages.append({"name": pkg_name, "version": pkg_version})

    # Sort packages deterministically by name
    packages.sort(key=lambda p: p["name"])
    return packages


def generate_cyclonedx_sbom(
    lockfile_path: Path | None = None, app_version: str | None = None
) -> dict[str, Any]:
    """Generate CycloneDX v1.6 JSON document from lockfile."""
    if lockfile_path is None:
        lockfile_path = _repo_root / "requirements" / "base.lock"

    if app_version is None:
        app_version = get_project_version()

    packages = parse_lockfile_packages(lockfile_path)

    # Compute deterministic UUID for serialNumber based on lockfile contents hash
    lock_hash = hashlib.sha256(
        lockfile_path.read_bytes() if lockfile_path.exists() else b""
    ).hexdigest()
    deterministic_uuid = str(uuid.UUID(hex=lock_hash[:32]))

    components: list[dict[str, Any]] = []
    for pkg in packages:
        p_name = pkg["name"]
        p_ver = pkg["version"]
        purl = f"pkg:pypi/{p_name}@{p_ver}"

        components.append(
            {
                "type": "library",
                "name": p_name,
                "version": p_ver,
                "purl": purl,
                "bom-ref": purl,
            }
        )

    sbom: dict[str, Any] = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "serialNumber": f"urn:uuid:{deterministic_uuid}",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "name": "gaiaos",
                "version": app_version,
            }
        },
        "components": components,
    }

    return sbom


def main() -> int:
    """CLI entrypoint for SBOM generation."""
    parser = argparse.ArgumentParser(
        description="Generate CycloneDX v1.6 SBOM JSON from lockfile."
    )
    parser.add_argument(
        "--lockfile",
        type=Path,
        default=_repo_root / "requirements" / "base.lock",
        help="Path to requirements lockfile",
    )
    parser.add_argument(
        "--version",
        type=str,
        default=None,
        help="Optional application version (defaults to version in pyproject.toml)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_repo_root / "gaiaos-sbom.json",
        help="Output path for generated gaiaos-sbom.json",
    )

    args = parser.parse_args()

    try:
        sbom_data = generate_cyclonedx_sbom(args.lockfile, app_version=args.version)
        formatted_json = json.dumps(sbom_data, indent=2) + "\n"

        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(formatted_json, encoding="utf-8")
        print(f"[OK] CycloneDX v1.6 SBOM generated successfully at {args.output}")
        return 0
    except Exception as exc:
        print(f"[ERROR] Failed to generate SBOM: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
