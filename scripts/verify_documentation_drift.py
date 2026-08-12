"""Dynamic documentation drift verification script for GaiaOS CI pipeline.

Discovers the current release version from pyproject.toml and verifies that
README.md, Architecture.md, and docs/releases/Versioning.md remain synchronized
with the current version, phase, and patch release series.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


def parse_pyproject_version(pyproject_path: Path) -> str | None:
    """Extract project version from pyproject.toml without external dependencies."""
    if not pyproject_path.exists():
        return None
    content = pyproject_path.read_text(encoding="utf-8")
    match = re.search(r'version\s*=\s*"([^"]+)"', content)
    return match.group(1) if match else None


def get_git_tags(repo_root: Path) -> list[str] | None:
    """Attempt to retrieve git tags from local repository if .git directory exists.

    Degrades gracefully by returning None if git metadata or CLI is unavailable.
    """
    git_dir = repo_root / ".git"
    if not git_dir.exists():
        return None
    try:
        res = subprocess.run(
            ["git", "tag", "-l"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if res.returncode == 0 and res.stdout:
            return [line.strip() for line in res.stdout.splitlines() if line.strip()]
    except Exception:
        pass
    return None


def verify_documentation_drift(
    repo_root: Path | None = None,
) -> tuple[bool, list[str]]:
    """Dynamically verify README.md, Architecture.md, and Versioning.md synchronization."""
    if repo_root is None:
        repo_root = Path(__file__).parent.parent

    pyproject_path = repo_root / "pyproject.toml"
    readme_path = repo_root / "README.md"
    versioning_path = repo_root / "docs" / "releases" / "Versioning.md"
    architecture_path = repo_root / "docs" / "Architecture.md"

    errors: list[str] = []

    version = parse_pyproject_version(pyproject_path)
    if not version:
        return False, [f"Could not parse 'version' from {pyproject_path}"]

    if not readme_path.exists():
        return False, [f"README.md not found at {readme_path}"]

    if not versioning_path.exists():
        return False, [f"Versioning.md not found at {versioning_path}"]

    if not architecture_path.exists():
        return False, [f"Architecture.md not found at {architecture_path}"]

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

    # Optional git tag comparison (degrades gracefully if git unavailable)
    git_tags = get_git_tags(repo_root)
    if git_tags:
        matching_prefix = f"v{major_str}.{minor_str}."
        series_tags = [t for t in git_tags if t.startswith(matching_prefix)]
        if series_tags:

            def parse_patch(t: str) -> int:
                try:
                    return int(t.split(".")[-1])
                except ValueError:
                    return -1

            max_tag_patch = max(parse_patch(t) for t in series_tags)
            if patch_str.isdigit() and int(patch_str) < max_tag_patch:
                target_tag = f"v{major_str}.{minor_str}.{max_tag_patch}"
                errors.append(f"pyproject.toml version ({version}) is behind git tag {target_tag}")

    readme_content = readme_path.read_text(encoding="utf-8")
    versioning_content = versioning_path.read_text(encoding="utf-8")
    architecture_content = architecture_path.read_text(encoding="utf-8")

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

    # 3. Verify Architecture.md contains reference to current phase
    if expected_phase not in architecture_content:
        errors.append(f"Architecture.md is missing reference to '{expected_phase}'")

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
