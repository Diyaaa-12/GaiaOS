# GaiaOS

[![CI](https://github.com/Diyaaa-12/GaiaOS/actions/workflows/ci.yml/badge.svg)](https://github.com/Diyaaa-12/GaiaOS/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

An Agentic Planetary Risk Intelligence Platform.

## Status

Phase 1, Phase 2, Phase 3, Phase 4, and v4.x Open Source Readiness Series (v4.1.0, v4.2.0) — Complete

| Milestone | Scope / Deliverable | Status |
|-----------|---------------------|--------|
| **Phase 1** | Foundation, FastAPI, PostgreSQL (PostGIS + pgvector), Docker, Gateway | Complete |
| **Phase 2** | Multi-Agent Reasoning Core, LangGraph, Literature RAG, Scorer | Complete |
| **Phase 3 — Milestones 1–10** | JWT/API Key Auth, Redis Rate Limiting, RQ Workers, SSE Stream, Eval Suite, Replan Loop, PostGIS, Ingestion, Metrics | Complete |
| **Phase 4 — Milestones 1–10** | CI Integrity, Auth Review, Monitoring/Alerting, Citation IDs, Geocoding, Disaster Recovery, Worker Scaling, Agent Contribution Framework, Admin UI, OpenAPI Publishing | Complete |
| **v4.1.0** | Repository Governance, Security Policy, Apache 2.0 License, Issue/PR Templates | Complete |
| **v4.2.0** | Community Health, Contributor Experience, Support Guidelines & Issue Triage Taxonomy | Complete |

Detailed architectural specifications and milestone scope documents are linked below:
- **Architecture**: [`docs/Architecture.md`](docs/Architecture.md)
- **Roadmaps**: [`docs/Roadmap_Phase1.md`](docs/Roadmap_Phase1.md), [`docs/Roadmap_Phase2.md`](docs/Roadmap_Phase2.md), [`docs/Roadmap_Phase3.md`](docs/Roadmap_Phase3.md), [`docs/Roadmap_Phase4.md`](docs/Roadmap_Phase4.md)
- **Versioning Strategy**: [`docs/releases/Versioning.md`](docs/releases/Versioning.md)

## Core Architecture

GaiaOS is structured into four primary layers:

- **API & Gateway (`app/`, `gateway/`, `auth/`)**: FastAPI REST and SSE endpoints with JWT/API key authentication and Redis rate limiting.
- **Reasoning Core (`orchestrator/`)**: LangGraph engine coordinating domain-specific risk agents (seismic, atmosphere, ocean, wildfire, air quality, RAG, causal chain, simulation, synthesis, critic).
- **Background Worker & Task System (`workers/`, `alerting/`, `ops/`)**: RQ worker pool for asynchronous investigation jobs, hazard ingestion, alert evaluation, and automated database backups.
- **Observability & Operations (`metrics/`, `alerting/`, `admin_ui/`, `ops/`)**: Metrics pipeline, threshold alerts, React/TypeScript Admin UI, and operational runbooks.

## Quick Start

### Prerequisites
- Python 3.12 (pinned in [`.python-version`](.python-version))
- Node.js 18+ & npm (for `admin_ui/`)
- Docker Engine 24+ & Docker Compose v2

### Setup & Local Execution

```bash
# Clone & virtualenv setup
git clone https://github.com/Diyaaa-12/GaiaOS.git
cd GaiaOS
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\Activate.ps1

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

## Development & Testing

```bash
# Run pytest test suite
pytest

# Code linting & type checks
ruff check .
mypy .

# Deterministic OpenAPI spec generation
python scripts/generate_openapi_spec.py
```

## Community & Support

We welcome contributions and community involvement!

- **Community Support & Q&A**: Read [`SUPPORT.md`](SUPPORT.md) for details on asking questions and finding support channels.
- **First-Time Contributors**: Explore issues tagged [`good first issue`](https://github.com/Diyaaa-12/GaiaOS/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) and [`help wanted`](https://github.com/Diyaaa-12/GaiaOS/issues?q=is%3Aissue+is%3Aopen+label%3A%22help+wanted%22).
- **Domain Agent Contributions**: See the [Domain Agent Contribution Guide](docs/CONTRIBUTING_AGENTS.md).
- **Security Policy**: Read [`SECURITY.md`](SECURITY.md) for private vulnerability reporting.
- **Code of Conduct**: Read [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

## Documentation & Operations Hub

GaiaOS uses dedicated documentation for specific workflows:

- **Project Versioning Strategy**: [`docs/releases/Versioning.md`](docs/releases/Versioning.md)
- **API Specification & Versioning**: [`docs/api/CHANGELOG.md`](docs/api/CHANGELOG.md) & [`docs/api/openapi/openapi.json`](docs/api/openapi/openapi.json)
- **Domain Agent Contribution Guide**: [`docs/CONTRIBUTING_AGENTS.md`](docs/CONTRIBUTING_AGENTS.md)
- **General Contributing Guidelines**: [`CONTRIBUTING.md`](CONTRIBUTING.md)
- **Community Support Guidelines**: [`SUPPORT.md`](SUPPORT.md)
- **Security Policy**: [`SECURITY.md`](SECURITY.md)
- **Code of Conduct**: [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md)
- **License**: [`LICENSE`](LICENSE) (Apache 2.0)
- **Admin Observability Dashboard**: [`docs/phase4/admin_dashboard.md`](docs/phase4/admin_dashboard.md)
- **Disaster Recovery Runbook**: [`ops/runbooks/disaster_recovery.md`](ops/runbooks/disaster_recovery.md)
- **Incident Response Runbook**: [`ops/runbooks/incident_response.md`](ops/runbooks/incident_response.md)
- **Migration Rollback Runbook**: [`ops/runbooks/migration_rollback.md`](ops/runbooks/migration_rollback.md)

## Continuous Integration

GitHub Actions workflow (`.github/workflows/ci.yml`) enforces:
- Ruff linting and Mypy type validation
- Pytest suite execution
- OpenAPI specification drift detection (`python scripts/generate_openapi_spec.py` vs `git diff --exit-code`)
- Container image build & health verification (`app`, `worker`, `scheduler`, `admin_ui`)
