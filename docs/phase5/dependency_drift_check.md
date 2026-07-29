# Dependency Range Drift & Lockfile Resolution — Phase 5 Reference

**Validation Script:** [`scripts/check_requirements_drift.py`](../../scripts/check_requirements_drift.py)  
**Lockfile Resolution Script:** [`scripts/regenerate_lockfiles.py`](../../scripts/regenerate_lockfiles.py)  
**CI Workflow:** [`.github/workflows/dependency-range-check.yml`](../../.github/workflows/dependency-range-check.yml)

## Overview

GaiaOS enforces strict, multi-layer dependency hygiene:

1. **Deterministic Repository Integrity Checker (`check_requirements_drift.py`)**:
   - Primary repository integrity gate operating purely on static local `.txt` and `.lock` files.
   - Asserts that every pinned version in `.lock` satisfies the declared range in `.txt`.
   - 100% deterministic across all operating systems, CI runners, and offline environments.

2. **Lockfile Generation (`regenerate_lockfiles.py`)**:
   - Uses `pip`'s dependency resolver (`pip install --dry-run --report`) to produce reproducible lockfiles directly from `.txt` requirements without text replacement.
   - **Canonical Generation Environment**: Linux (Ubuntu 22.04+ / `ubuntu-latest`) + Python 3.12.
   - **Platform-Neutral Marker Filtering**: Environment markers (e.g., `sys_platform == "win32"`) are evaluated against the canonical environment context (`CANONICAL_ENV`).
   - **Reachability Policy**: A dependency is retained if it is reachable through at least one requirement whose environment marker evaluates true in the canonical environment.

## Usage

```bash
# Deterministic repository integrity validation
python scripts/check_requirements_drift.py requirements/base.txt requirements/base.lock
python scripts/check_requirements_drift.py requirements/dev.txt requirements/dev.lock

# Regenerate lockfiles using pip's dependency resolver
python scripts/regenerate_lockfiles.py

# Verify lockfiles match pip dependency resolution output (used in CI)
python scripts/regenerate_lockfiles.py --check
```

## Security & Workflow Model

- **Safe CI Permission Model**: Uses standard `pull_request` event with read-only permissions (`contents: read`). Avoids `pull_request_target` and write-token permissions.
- **No Text Replacement**: Lockfiles are generated using `pip`'s dependency resolver, guaranteeing valid dependency graphs.
