# Development & CI Verification Workflow Guide

[Documentation Hub](../README.md) | [Environment Setup](ENVIRONMENT_SETUP.md) | [First PR Guide](FIRST_PR.md) | [How-To Guides](HOW_TO_GUIDES.md)

---

GaiaOS enforces strict continuous integration (CI) quality gates on every push and pull request via GitHub Actions (`.github/workflows/ci.yml`).

To maintain **100% parity between your local environment and CI**, GaiaOS provides a unified 5-step local verification workflow that can be executed as a single command or run individually.

---

## ⚡ Unified Local Verification Command

Run the entire local quality suite with one command before committing or pushing changes:

```bash
python scripts/verify.py
```

> [!TIP]
> **Fast Lint & Type Check Option**: If you want to quickly check linting and static types while making active edits (skipping the full unit test execution), pass the `--skip-tests` flag:
> ```bash
> python scripts/verify.py --skip-tests
> ```

---

## 🛠️ The 5 Verification Pillars (Individual CLI Commands)

You can also run each step of the verification pipeline individually during development:

### 1. Code Format & Linting (`ruff`)
GaiaOS uses [Ruff](https://github.com/astral-sh/ruff) for fast Python linting and code formatting analysis.

```bash
# Check code for linting issues
ruff check .

# Automatically fix auto-fixable lint issues
ruff check --fix .
```

### 2. Static Type Checking (`mypy`)
GaiaOS enforces strict static type hints using [Mypy](https://mypy-lang.org/).

```bash
mypy .
```

### 3. Test Suite Execution (`pytest`)
GaiaOS uses [Pytest](https://docs.pytest.org/) for unit, integration, and contract tests.

```bash
# Run full pytest suite
pytest

# Run tests with verbose output
pytest -v

# Run a specific test file
pytest tests/test_seismic_agent.py

# Run tests matching a specific expression
pytest -k "test_health"
```

### 4. OpenAPI Specification Drift Check (`generate_openapi_spec.py`)
To prevent contract drift between FastAPI route handlers and the checked-in OpenAPI JSON spec:

```bash
# Generate the deterministic OpenAPI spec file
python scripts/generate_openapi_spec.py

# Verify zero uncommitted drift in git
git diff --exit-code docs/api/openapi/openapi.json
```

If `git diff` returns an exit code of `1`, commit the updated `docs/api/openapi/openapi.json` file.

### 5. Docker Container Smoke Verification
To verify that app, background worker, and scheduler container images build and launch cleanly:

```bash
# Spin up services via Docker Compose
docker compose up -d --build --wait app worker scheduler

# Check HTTP health endpoint
curl --fail http://localhost:8000/api/v1/health/live

# Run worker container smoke test
python -m tests.test_worker_image_smoke
```

---

## 🔄 GitHub Actions CI Parity Table

Here is how local verification commands map directly to `.github/workflows/ci.yml`:

| Local Verification Command | GitHub Actions CI Step | Purpose |
|----------------------------|------------------------|---------|
| `ruff check .` | `Run Ruff` | Code quality and lint rules |
| `mypy .` | `Run Mypy` | Type safety verification |
| `pytest` | `Run Pytest` | Test suite pass guarantee |
| `python scripts/generate_openapi_spec.py` | `Verify OpenAPI specification drift` | Detect out-of-sync API contracts |
| `docker compose up -d --build --wait` | `Build and verify container images` | Production container sanity check |
| **`python scripts/verify.py`** | **Full CI Job Sequence** | **Runs all steps locally in one command** |
