"""GaiaOS Release Readiness Verification Script.

Validates that a release tag follows semantic versioning rules (v0.X.Y or v0.X.Y-rcZ)
and verifies that docs/releases/Versioning.md contains an exact documented entry
describing the release tag before publishing.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Repository root directory
_repo_root = Path(__file__).resolve().parent.parent

# Semver tag format regex: vX.Y.Z or vX.Y.Z-rcW (e.g., v1.0.0 or v1.0.0-rc1)
TAG_REGEX = re.compile(r"^v\d+\.\d+\.\d+(-rc\d+)?$")



def validate_tag_format(tag: str) -> bool:
    """Check if the release tag matches expected semver format (vX.Y.Z or vX.Y.Z-rcW)."""
    return bool(TAG_REGEX.match(tag))


def verify_versioning_doc(tag: str, versioning_doc_path: Path | None = None) -> bool:
    """Verify that docs/releases/Versioning.md contains an entry for the release tag."""
    if versioning_doc_path is None:
        versioning_doc_path = _repo_root / "docs" / "releases" / "Versioning.md"

    if not versioning_doc_path.exists():
        print(f"[ERROR] Versioning doc not found at {versioning_doc_path}", file=sys.stderr)
        return False

    content = versioning_doc_path.read_text(encoding="utf-8")

    # Search for tag string in the versioning document (e.g. '| v1.0.0 |' or '**v1.0.0**')

    if tag in content:
        return True

    return False


def verify_release_readiness(
    tag: str, versioning_doc_path: Path | None = None
) -> tuple[bool, str]:
    """Verify overall release readiness for a tag.

    Returns:
        (is_ready, message)
    """
    if not validate_tag_format(tag):
        return False, (
            f"[ERROR] Invalid release tag format: '{tag}'. "
            "Release tags must match vX.Y.Z or vX.Y.Z-rcW (e.g., v1.0.0 or v1.0.0-rc1)."
        )

    if not verify_versioning_doc(tag, versioning_doc_path):
        return False, (
            f"[ERROR] Release Gate Failed: Tag '{tag}' is not described in "
            "docs/releases/Versioning.md. Please update docs/releases/Versioning.md "
            "with release notes and tag entry before pushing tag."
        )

    return True, f"[OK] Release readiness gate passed for tag '{tag}'."


def main() -> int:
    """CLI entrypoint for release readiness verification."""
    parser = argparse.ArgumentParser(
        description="Verify release tag format and docs/releases/Versioning.md entry."
    )
    parser.add_argument(
        "--tag",
        required=True,
        help="Release tag name to verify (e.g., v1.0.0)",
    )

    parser.add_argument(
        "--versioning-doc",
        type=Path,
        default=None,
        help="Optional path to Versioning.md document",
    )

    args = parser.parse_args()
    is_ready, message = verify_release_readiness(args.tag, args.versioning_doc)

    if not is_ready:
        print(message, file=sys.stderr)
        return 1

    print(message)
    return 0


if __name__ == "__main__":
    sys.exit(main())
