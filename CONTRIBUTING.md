# Contributing to GaiaOS

Thank you for your interest in contributing to GaiaOS! GaiaOS is an Agentic Planetary Risk Intelligence Platform built following a structured, milestone-oriented release strategy (see [`docs/releases/Versioning.md`](docs/releases/Versioning.md)).

---

## Documentation & Navigation

Before starting work, review our central documentation guides:

- **[Documentation Hub](docs/README.md)** — Primary navigation entry point for all system specifications and guides.
- **[Environment Setup Guide](docs/contributing/ENVIRONMENT_SETUP.md)** — OS-specific setup (Windows, Linux, macOS), troubleshooting, and FAQ.
- **[First Pull Request Walkthrough](docs/contributing/FIRST_PR.md)** — Step-by-step walkthrough for first-time contributors.
- **[Project Structure & Code Placement Guide](docs/contributing/PROJECT_STRUCTURE.md)** — Codebase map and *"Where should I add new code?"* matrix.
- **[Step-by-Step How-To Guides](docs/contributing/HOW_TO_GUIDES.md)** — Procedures for adding agents, APIs, models, tests, and spec updates.
- **[Development & CI Workflow Guide](docs/contributing/DEVELOPMENT_WORKFLOW.md)** — Quality checks, verification tools, and CI parity.

---

## Getting Started & Support

Before starting work, please review our core community guidelines:

- **Need Help / Have Questions?** Check [`SUPPORT.md`](SUPPORT.md) for community support guidelines, Q&A channels, and maintainer expectations.
- **Security Vulnerabilities**: Read [`SECURITY.md`](SECURITY.md) to report vulnerabilities privately via GitHub Private Security Advisories.
- **Code of Conduct**: All community members and contributors must adhere to our [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

---

## Finding an Issue to Work On

We welcome contributions of all sizes! Look for issues in our tracker with these tags:

- **[`good first issue`](https://github.com/Diyaaa-12/GaiaOS/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)**: Small, self-contained issues perfect for first-time contributors.
- **[`help wanted`](https://github.com/Diyaaa-12/GaiaOS/issues?q=is%3Aissue+is%3Aopen+label%3A%22help+wanted%22)**: Tasks where community assistance is actively sought.

If you want to contribute a new domain-specific risk agent (e.g. seismic, wildfire, atmospheric), please follow the dedicated [Domain Agent Contribution Guide](docs/CONTRIBUTING_AGENTS.md).

---

## Branching Convention & Workflow

- **`main`**: Stable branch representing the latest completed release milestone.
- **`feature/<milestone-name>`**: Feature branches scoped to specific milestone deliverables (e.g., `feature/agent-contract-check`).

### Workflow Steps

1. Fork the repository and create your branch from `main`:
   ```bash
   git checkout -b feature/short-descriptive-name
   ```
2. Implement your changes following the active milestone scope or open issue acceptance criteria.
3. Verify your changes locally using automated quality checks (see below).
4. Submit a Pull Request targeting `main`.

For a full step-by-step walkthrough, see the [First PR Walkthrough](docs/contributing/FIRST_PR.md).

---

## Local Development Setup

GaiaOS requires Python **3.12** (pinned in [`.python-version`](.python-version) and enforced in [`pyproject.toml`](pyproject.toml)), Docker Engine 24+, and Docker Compose v2.

```bash
# Clone & virtualenv setup
git clone https://github.com/Diyaaa-12/GaiaOS.git
cd GaiaOS
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .\.venv\Scripts\Activate.ps1

# Install dependencies using canonical lockfile
pip install -r requirements/dev.lock

# Copy environment configs
cp .env.example .env
cp docker-compose.override.yml.example docker-compose.override.yml

# Start full stack via Docker Compose
docker compose up -d --build
```

For OS-specific setup notes (Windows execution policy, line endings, troubleshooting), refer to the canonical **[Environment Setup Guide](docs/contributing/ENVIRONMENT_SETUP.md)**.


---

## Local Automated Verification

Before submitting a PR, ensure all local automated checks pass cleanly.

### Option A: Unified Local CI Verification Script (Recommended)
```bash
python scripts/verify.py
```

### Option B: Individual Step Execution
```bash
# 1. Code linting
ruff check .

# 2. Static type checking
mypy .

# 3. Test suite
pytest

# 4. OpenAPI spec drift verification
python scripts/generate_openapi_spec.py
git diff --exit-code docs/api/openapi/openapi.json
```

For complete workflow details, see the [Development & CI Workflow Guide](docs/contributing/DEVELOPMENT_WORKFLOW.md).

---

## Pull Request Guidelines & Checklist

Every pull request uses our standard [PR Template](.github/PULL_REQUEST_TEMPLATE.md) and requires:

- **Focused Scope**: Keep PRs focused on a single feature, bug fix, or documentation enhancement.
- **Test Coverage**: Include unit or integration tests for new code paths.
- **Documentation**: Update docstrings, README, or per-milestone `docs/` files if affected.
- **Commit Messages**: Write clear, descriptive commit messages explaining *why* changes were made.


