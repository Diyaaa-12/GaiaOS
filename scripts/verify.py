"""Lightweight CLI tool for running full local verification suite in GaiaOS.

Orchestrates existing verification commands to ensure parity with GitHub Actions CI.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

# Repository root directory
REPO_ROOT = Path(__file__).resolve().parent.parent


def run_step(name: str, cmd: list[str]) -> bool:
    """Run a single verification step and print formatted status output."""
    print("\n==================================================")
    print(f"   Step: {name}")
    print(f"   Command: {' '.join(cmd)}")
    print("==================================================")

    start_time = time.time()
    result = subprocess.run(cmd, cwd=REPO_ROOT)
    elapsed = time.time() - start_time

    if result.returncode == 0:
        print(f"-> PASSED [{name}] ({elapsed:.2f}s)")
        return True
    else:
        print(f"-> FAILED [{name}] with exit code {result.returncode} ({elapsed:.2f}s)")
        return False


def verify_openapi_drift() -> bool:
    """Generate OpenAPI spec and verify zero uncommitted drift."""
    print("\n==================================================")
    print("   Step: OpenAPI Spec Drift Check")
    print("   Command: python scripts/generate_openapi_spec.py & git diff --exit-code")
    print("==================================================")

    start_time = time.time()
    gen_result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "generate_openapi_spec.py")],
        cwd=REPO_ROOT,
    )
    if gen_result.returncode != 0:
        print(f"-> FAILED [OpenAPI Generation] with exit code {gen_result.returncode}")
        return False

    diff_result = subprocess.run(
        ["git", "diff", "--exit-code", "docs/api/openapi/openapi.json"],
        cwd=REPO_ROOT,
    )
    elapsed = time.time() - start_time

    if diff_result.returncode == 0:
        print(f"-> PASSED [OpenAPI Spec Drift Check] ({elapsed:.2f}s)")
        return True
    else:
        print(
            "-> FAILED [OpenAPI Spec Drift Check]. Specification file "
            "docs/api/openapi/openapi.json has uncommitted changes. "
            "Run 'python scripts/generate_openapi_spec.py' and commit."
        )
        return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run local GaiaOS verification suite (Ruff, Mypy, Pytest, OpenAPI drift)."
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip running pytest test suite (useful for fast lint/type check).",
    )
    args = parser.parse_args()

    steps: list[tuple[str, list[str]]] = [
        ("Ruff Linting", [sys.executable, "-m", "ruff", "check", "."]),
        ("Mypy Static Type Checking", [sys.executable, "-m", "mypy", "."]),
    ]

    if not args.skip_tests:
        steps.append(("Pytest Test Suite", [sys.executable, "-m", "pytest"]))

    passed = True
    for name, cmd in steps:
        if not run_step(name, cmd):
            passed = False

    if not verify_openapi_drift():
        passed = False

    print("\n--------------------------------------------------")
    if passed:
        print(" SUCCESS: All local verification checks passed cleanly!")
        sys.exit(0)
    else:
        print(" FAILURE: One or more verification checks failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
