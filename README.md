# GaiaOS

[![CI](https://github.com/Diyaaa-12/GaiaOS/actions/workflows/ci.yml/badge.svg)](https://github.com/Diyaaa-12/GaiaOS/actions/workflows/ci.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](.python-version)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

An Agentic Planetary Risk Intelligence Platform.

## Status

Phase 1, Phase 2, Phase 3, Phase 4, and v4.x Open Source Readiness Series (v4.1.0, v4.2.0, v4.3.0) — Complete

| Milestone | Scope / Deliverable | Status |
|-----------|---------------------|--------|
| **Phase 1** | Foundation, FastAPI, PostgreSQL (PostGIS + pgvector), Docker, Gateway | Complete |
| **Phase 2** | Multi-Agent Reasoning Core, LangGraph, Literature RAG, Scorer | Complete |
| **Phase 3 — Milestones 1–10** | JWT/API Key Auth, Redis Rate Limiting, RQ Workers, SSE Stream, Eval Suite, Replan Loop, PostGIS, Ingestion, Metrics | Complete |
| **Phase 4 — Milestones 1–10** | CI Integrity, Auth Review, Monitoring/Alerting, Citation IDs, Geocoding, Disaster Recovery, Worker Scaling, Agent Contribution Framework, Admin UI, OpenAPI Publishing | Complete |
| **v4.1.0** | Repository Governance, Security Policy, Apache 2.0 License, Issue/PR Templates | Complete |
| **v4.2.0** | Community Health, Contributor Experience, Support Guidelines & Issue Triage Taxonomy | Complete |
| **v4.3.0** | Contributor Experience: Onboarding UX, Architecture Navigation, Contributor Guides, Developer Tooling & Local CI Parity | Complete |

Detailed architectural specifications, documentation hub, and milestone scope documents are linked below:
- **Documentation Hub**: [`docs/README.md`](docs/README.md)
- **Architecture**: [`docs/Architecture.md`](docs/Architecture.md)
- **Roadmaps**: [`docs/Roadmap_Phase1.md`](docs/Roadmap_Phase1.md), [`docs/Roadmap_Phase2.md`](docs/Roadmap_Phase2.md), [`docs/Roadmap_Phase3.md`](docs/Roadmap_Phase3.md), [`docs/Roadmap_Phase4.md`](docs/Roadmap_Phase4.md)
- **Versioning Strategy**: [`docs/releases/Versioning.md`](docs/releases/Versioning.md)

## Core Architecture

GaiaOS is structured into four primary layers:

- **API & Gateway (`app/`, `gateway/`, `auth/`)**: FastAPI REST and SSE endpoints with JWT/API key authentication and Redis rate limiting.
- **Reasoning Core (`orchestrator/`)**: LangGraph engine coordinating domain-specific risk agents (seismic, atmosphere, ocean, wildfire, air quality, RAG, causal chain, simulation, synthesis, critic).
- **Background Worker & Task System (`workers/`, `alerting/`, `ops/`)**: RQ worker pool for asynchronous investigation jobs, hazard ingestion, alert evaluation, and automated database backups.
- **Observability & Operations (`metrics/`, `alerting/`, `admin_ui/`, `ops/`)**: Metrics pipeline, threshold alerts, React/TypeScript Admin UI, and operational runbooks.

For repository folder trees and code placement guidance, see [Project Structure & Code Placement](docs/contributing/PROJECT_STRUCTURE.md).

## Quick Start

### Prerequisites
- Python 3.12 (pinned in [`.python-version`](.python-version))
- Node.js 18+ & npm (for `admin_ui/`)
- Docker Engine 24+ & Docker Compose v2

For detailed OS-specific setup (Windows, Linux, macOS), see the [Environment Setup Guide](docs/contributing/ENVIRONMENT_SETUP.md).

### Setup & Local Execution

```bash
# Clone & virtualenv setup
git clone https://github.com/Diyaaa-12/GaiaOS.git
cd GaiaOS
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .\.venv\Scripts\Activate.ps1

# Install dependencies using pinned lockfile
pip install -r requirements/dev.lock

# Copy environment configs
cp .env.example .env
cp docker-compose.override.yml.example docker-compose.override.yml

# Start full stack via Docker Compose
docker compose up -d --build
```

**Services**:
- API Server & OpenAPI UI: `http://localhost:8000/docs`
- Admin Dashboard: `http://localhost:3000`

## Development & Local Verification

GaiaOS provides a unified local verification tool (`scripts/verify.py`) as well as individual verification commands:

```bash
# Unified local CI verification
python scripts/verify.py

# Or run individual checks:
ruff check .
mypy .
pytest
python scripts/generate_openapi_spec.py
```

See the [Development & CI Workflow Guide](docs/contributing/DEVELOPMENT_WORKFLOW.md) for complete details.

## Community & Support

We welcome contributions and community involvement!

- **Central Documentation Hub**: Explore [`docs/README.md`](docs/README.md).
- **First-Time Contributors**: Read our [First PR Guide](docs/contributing/FIRST_PR.md) and explore issues tagged [`good first issue`](https://github.com/Diyaaa-12/GaiaOS/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22).
- **Step-by-Step How-To Guides**: See [How-To Guides](docs/contributing/HOW_TO_GUIDES.md) for adding agents, APIs, models, and tests.
- **Domain Agent Contributions**: See the [Domain Agent Contribution Guide](docs/CONTRIBUTING_AGENTS.md).
- **Community Support & Q&A**: Read [`SUPPORT.md`](SUPPORT.md).
- **Security Policy**: Read [`SECURITY.md`](SECURITY.md).
- **Code of Conduct**: Read [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

## Documentation & Navigation

All architectural specifications, contributor guides, API schemas, release notes, operational runbooks, and audit reports are indexed in the [Documentation Hub](docs/README.md).

- **[Documentation Hub](docs/README.md)** — Complete index of all project documentation.
- **[Contributing Guidelines](CONTRIBUTING.md)** — Governance, branching strategy, and PR requirements.
- **[Support & Q&A](SUPPORT.md)** — Community support channels, issue triage taxonomy, and SLA.
- **[Security Policy](SECURITY.md)** — Vulnerability reporting and security disclosures.

## Continuous Integration

GitHub Actions workflow (`.github/workflows/ci.yml`) enforces:
- Ruff linting and Mypy type validation
- Pytest suite execution
- OpenAPI specification drift detection (`python scripts/generate_openapi_spec.py` vs `git diff --exit-code`)
- Container image build & health verification (`app`, `worker`, `scheduler`, `admin_ui`)



