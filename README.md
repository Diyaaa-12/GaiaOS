# GaiaOS

[![CI](https://github.com/Diyaaa-12/GaiaOS/actions/workflows/ci.yml/badge.svg)](https://github.com/Diyaaa-12/GaiaOS/actions/workflows/ci.yml)

An Agentic Planetary Risk Intelligence Platform.

## Status

Phase 1, Phase 2, Phase 3, and Phase 4 — Complete

| Milestone | Scope / Deliverable | Status |
|-----------|---------------------|--------|
| **Phase 1** | Foundation, FastAPI, PostgreSQL (PostGIS + pgvector), Docker, Gateway | Complete |
| **Phase 2** | Multi-Agent Reasoning Core, LangGraph, Literature RAG, Scorer | Complete |
| **Phase 3 — Milestones 1–10** | JWT/API Key Auth, Redis Rate Limiting, RQ Workers, SSE Stream, Eval Suite, Replan Loop, PostGIS, Ingestion, Metrics | Complete |
| **Phase 4 — Milestone 1** | CI/Deployment Integrity & Supply-Chain Hardening | Complete |
| **Phase 4 — Milestone 2** | Authentication Security Review & Hardening | Complete |
| **Phase 4 — Milestone 3** | Production Monitoring & Alerting | Complete |
| **Phase 4 — Milestone 4** | Citation Integrity Upgrade (Evidence IDs) | Complete |
| **Phase 4 — Milestone 5** | Geocoding & Shared HTTP Client Data Quality | Complete |
| **Phase 4 — Milestone 6** | Database Backup & Disaster Recovery | Complete |
| **Phase 4 — Milestone 7** | Advisory Worker Pool Scaling Policy | Complete |
| **Phase 4 — Milestone 8** | Agent Contribution Framework | Complete |
| **Phase 4 — Milestone 9** | Operational Observability Dashboard (Admin UI) | Complete |
| **Phase 4 — Milestone 10** | Public Documentation, API Spec Publishing & README Overhaul | Complete |

Detailed architectural specifications and milestone scope documents are linked below:
- **Architecture**: [`docs/Architecture.md`](docs/Architecture.md)
- **Roadmaps**: [`docs/Roadmap_Phase1.md`](docs/Roadmap_Phase1.md), [`docs/Roadmap_Phase2.md`](docs/Roadmap_Phase2.md), [`docs/Roadmap_Phase3.md`](docs/Roadmap_Phase3.md), [`docs/Roadmap_Phase4.md`](docs/Roadmap_Phase4.md)

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

# Install dependencies
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

## Documentation & Operations Hub

GaiaOS uses dedicated documentation for specific workflows:

- **Project Versioning Strategy**: [`docs/releases/Versioning.md`](docs/releases/Versioning.md)
- **API Specification & Versioning**: [`docs/api/CHANGELOG.md`](docs/api/CHANGELOG.md) & [`docs/api/openapi/openapi.json`](docs/api/openapi/openapi.json)
- **Domain Agent Contribution Guide**: [`docs/CONTRIBUTING_AGENTS.md`](docs/CONTRIBUTING_AGENTS.md)
- **General Contributing Guidelines**: [`CONTRIBUTING.md`](CONTRIBUTING.md)
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
