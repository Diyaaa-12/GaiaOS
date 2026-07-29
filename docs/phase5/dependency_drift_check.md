# Dependency Range Drift Check — Phase 5 Reference

**Script:** [`scripts/check_requirements_drift.py`](../../scripts/check_requirements_drift.py)  
**CI Workflow:** [`.github/workflows/dependency-range-check.yml`](../../.github/workflows/dependency-range-check.yml)

## Overview

The dependency range drift checker verifies that pinned package versions in lockfiles (`.lock`) satisfy the version range specifiers declared in requirements files (`.txt`).

## Usage

```bash
# Validate base runtime requirements
python scripts/check_requirements_drift.py requirements/base.txt requirements/base.lock

# Validate development requirements
python scripts/check_requirements_drift.py requirements/dev.txt requirements/dev.lock
```

## Validation Rules

1. Parses package requirement range specifiers from `.txt` files (processing recursive `-r` includes).
2. Parses pinned package versions from `.lock` files (processing recursive `-r` includes).
3. Verifies that every package declared in `.txt` has a pinned version in `.lock` that satisfies the range specifier.
4. Ignores transitive-only dependencies present in `.lock`.
5. Exits with status `1` and outputs failure details if a declared dependency is missing from the lockfile or if the locked version violates the declared version range.
# Verify lockfiles match pip dependency resolution output (used in CI)
python scripts/regenerate_lockfiles.py --check
```

## Security & Workflow Model

- **Safe CI Permission Model**: Uses standard `pull_request` event with read-only permissions (`contents: read`). Avoids `pull_request_target` and write-token permissions.
- **No Text Replacement**: Lockfiles are generated using `pip`'s dependency resolver, guaranteeing valid dependency graphs.
