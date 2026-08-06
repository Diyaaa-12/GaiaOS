"""Dynamic documentation drift verification script for GaiaOS CI pipeline.

Discovers the current release version from pyproject.toml and verifies that
README.md and docs/releases/Versioning.md remain synchronized with the current
version, phase, and patch release series.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


def parse_pyproject_version(pyproject_path: Path) -> str | None:
    """Extract project version from pyproject.toml without external dependencies."""
    if not pyproject_path.exists():
        return None
    content = pyproject_path.read_text(encoding="utf-8")
    match = re.search(r'version\s*=\s*"([^"]+)"', content)
    return match.group(1) if match else None


def verify_documentation_drift(
    repo_root: Path | None = None,
) -> tuple[bool, list[str]]:
    """Dynamically verify README.md and Versioning.md are synchronized with pyproject.toml."""
    if repo_root is None:
        repo_root = Path(__file__).parent.parent

    pyproject_path = repo_root / "pyproject.toml"
    readme_path = repo_root / "README.md"
    versioning_path = repo_root / "docs" / "releases" / "Versioning.md"

    errors: list[str] = []

    version = parse_pyproject_version(pyproject_path)
    if not version:
        return False, [f"Could not parse 'version' from {pyproject_path}"]

    if not readme_path.exists():
        return False, [f"README.md not found at {readme_path}"]

    if not versioning_path.exists():
        return False, [f"Versioning.md not found at {versioning_path}"]

    # Derive expected phase and release tag series from version
    latest_tag = f"v{version}"
    parts = version.split(".")
    if len(parts) < 3:
        return False, [f"Invalid semver string '{version}' in pyproject.toml"]

    major_str, minor_str, patch_str = parts[0], parts[1], parts[2]
    expected_phase = f"Phase {minor_str}"

    try:
        patch_int = int(patch_str)
        expected_series_versions = [
            f"v{major_str}.{minor_str}.{p}" for p in range(patch_int + 1)
        ]
    except ValueError:
        expected_series_versions = [latest_tag]

    readme_content = readme_path.read_text(encoding="utf-8")
    versioning_content = versioning_path.read_text(encoding="utf-8")

    # 1. Verify README.md contains expected phase and latest version
    if expected_phase not in readme_content:
        errors.append(f"README.md is missing reference to '{expected_phase}'")

    if latest_tag not in readme_content:
        errors.append(f"README.md is missing reference to latest tag '{latest_tag}'")

    for ver in expected_series_versions:
        if ver not in readme_content:
            errors.append(f"README.md status table is missing entry for version '{ver}'")

    # 2. Verify Versioning.md contains expected phase, latest tag, and series versions
    if expected_phase not in versioning_content:
        errors.append(f"Versioning.md is missing reference to '{expected_phase}'")

    if latest_tag not in versioning_content:
        errors.append(
            f"Versioning.md Release Map is missing reference to latest tag '{latest_tag}'"
        )

    for ver in expected_series_versions:
        if ver not in versioning_content:
            errors.append(f"Versioning.md Release Map is missing entry for version '{ver}'")

    is_valid = len(errors) == 0
    return is_valid, errors


def main() -> int:
    """CLI entry point for documentation drift check."""
    is_valid, errors = verify_documentation_drift()
    if not is_valid:
        print("[ERROR] Documentation Drift Verification Failed:\n", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print("[OK] Documentation drift check passed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
