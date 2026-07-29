"""Dependency range drift checker.

Validates that pinned package versions in a lockfile satisfy the version range
specifiers declared in a source requirements file.
"""

from __future__ import annotations

import sys
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


def parse_requirements_file(
    file_path: Path, visited: set[Path] | None = None
) -> dict[str, tuple[Requirement, Path, int]]:
    """Parse requirement specifiers from a .txt requirements file.

    Recursively processes included files via -r / --requirement.
    Returns a dict mapping canonical package names to (Requirement, file_path, line_no).
    """
    if visited is None:
        visited = set()

    resolved_path = file_path.resolve()
    if resolved_path in visited:
        return {}
    visited.add(resolved_path)

    requirements: dict[str, tuple[Requirement, Path, int]] = {}

    if not file_path.exists():
        raise FileNotFoundError(f"Requirements file not found: {file_path}")

    with open(file_path, encoding="utf-8") as f:
        for line_no, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            if line.startswith("-r ") or line.startswith("--requirement "):
                ref_filename = line.split(maxsplit=1)[1].strip()
                ref_path = file_path.parent / ref_filename
                nested_reqs = parse_requirements_file(ref_path, visited)
                requirements.update(nested_reqs)
                continue

            if line.startswith("-"):
                continue

            try:
                req = Requirement(line)
                canon_name = canonicalize_name(req.name)
                requirements[canon_name] = (req, file_path, line_no)
            except Exception as err:
                raise ValueError(
                    f"Invalid requirement specifier at {file_path}:{line_no}: '{line}' ({err})"
                ) from err

    return requirements


def parse_lock_file(
    file_path: Path, visited: set[Path] | None = None
) -> dict[str, tuple[str, Path, int]]:
    """Parse pinned package versions from a .lock file.

    Recursively processes included files via -r / --requirement.
    Returns a dict mapping canonical package names to (pinned_version, file_path, line_no).
    """
    if visited is None:
        visited = set()

    resolved_path = file_path.resolve()
    if resolved_path in visited:
        return {}
    visited.add(resolved_path)

    locked: dict[str, tuple[str, Path, int]] = {}

    if not file_path.exists():
        raise FileNotFoundError(f"Lock file not found: {file_path}")

    with open(file_path, encoding="utf-8") as f:
        for line_no, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            if line.startswith("-r ") or line.startswith("--requirement "):
                ref_filename = line.split(maxsplit=1)[1].strip()
                ref_path = file_path.parent / ref_filename
                nested_locked = parse_lock_file(ref_path, visited)
                locked.update(nested_locked)
                continue

            if line.startswith("-"):
                continue

            try:
                req = Requirement(line)
                canon_name = canonicalize_name(req.name)
                specifiers = list(req.specifier)
                if specifiers:
                    version_str = specifiers[0].version
                else:
                    version_str = ""
                locked[canon_name] = (version_str, file_path, line_no)
            except Exception as err:
                raise ValueError(
                    f"Invalid lock entry at {file_path}:{line_no}: '{line}' ({err})"
                ) from err

    return locked


def check_requirements_drift(txt_path: Path, lock_path: Path) -> list[str]:
    """Validate that pinned versions in lock_path satisfy ranges in txt_path.

    Returns a list of failure messages identifying package name, declared range,
    and locked version. An empty list indicates clean validation.
    """
    txt_reqs = parse_requirements_file(txt_path)
    lock_pins = parse_lock_file(lock_path)

    errors: list[str] = []

    for canon_name, (req, req_file, _line_no) in txt_reqs.items():
        if canon_name not in lock_pins:
            errors.append(
                f"Missing dependency: Package '{req.name}' (declared range: '{req.specifier}') "
                f"declared in '{req_file}' is missing from lock file '{lock_path}'."
            )
            continue

        pinned_version, _lock_file, _lock_line = lock_pins[canon_name]
        if not pinned_version:
            errors.append(
                f"Unpinned dependency: Package '{req.name}' in lock file '{lock_path}' "
                f"has no pinned version ('==x.y.z')."
            )
            continue

        if not req.specifier.contains(pinned_version, prereleases=True):
            errors.append(
                f"Version drift: Package '{req.name}' locked version '{pinned_version}' "
                f"does not satisfy declared range '{req.specifier}' from '{req_file}'."
            )

    return errors


def main() -> int:
    if len(sys.argv) != 3:
        print(
            "Usage: python scripts/check_requirements_drift.py "
            "<requirements.txt> <requirements.lock>",
            file=sys.stderr,
        )
        return 2

    txt_path = Path(sys.argv[1])
    lock_path = Path(sys.argv[2])

    errors = check_requirements_drift(txt_path, lock_path)
    if errors:
        print(
            f"ERROR: Dependency range drift check failed for {txt_path} vs {lock_path}:",
            file=sys.stderr,
        )
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print(f"SUCCESS: All declared requirements in {txt_path} are satisfied by {lock_path}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
