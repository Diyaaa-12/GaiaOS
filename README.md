# GaiaOS

[![CI](https://github.com/Diyaaa-12/GaiaOS/actions/workflows/ci.yml/badge.svg)](https://github.com/Diyaaa-12/GaiaOS/actions/workflows/ci.yml)

An Agentic Planetary Risk Intelligence Platform.

## Status

Phase 1, Phase 2, and Phase 3 — Complete

| Milestone | Status |
|-----------|--------|
| **Phase 1** — Foundation, FastAPI, PostgreSQL, Docker, Alembic, Gateway | Complete |
| **Phase 2** — Multi-Agent Reasoning Core, LangGraph, Literature RAG, Scorer | Complete |
| **Phase 3 — Milestone 1**: JWT Authentication & User Lifecycle | Complete |
| **Phase 3 — Milestone 2**: API Key Authorization & Redis Rate Limiting | Complete |
| **Phase 3 — Milestone 3**: RQ Worker Queue & Durable Task Execution | Complete |
| **Phase 3 — Milestone 4**: SSE Streaming Investigation Progress | Complete |
| **Phase 3 — Milestone 5**: Benchmark Suite & Regression Gate Expansion | Complete |
| **Phase 3 — Milestone 6**: Bounded Replan Loop (Self-Correction) | Complete |
| **Phase 3 — Milestone 7**: PostGIS Geometry Migration & Geospatial Reasoning | Complete |
| **Phase 3 — Milestone 8**: Real Hazard Event Ingestion Pipeline | Complete |
| **Phase 3 — Milestone 9**: Aggregated Observability & Metrics API | Complete |
| **Phase 3 — Milestone 10**: API Hardening & Public Versioning | Complete |

Architecture is frozen in [`docs/Architecture.md`](docs/Architecture.md). Phase 1, 2, and 3 scopes are detailed in [`docs/Roadmap_Phase1.md`](docs/Roadmap_Phase1.md), [`docs/Roadmap_Phase2.md`](docs/Roadmap_Phase2.md), and [`docs/Roadmap_Phase3.md`](docs/Roadmap_Phase3.md).

## Prerequisites

- **Git**
- **Python 3.12** — version pinned in [`.python-version`](.python-version) and [`pyproject.toml`](pyproject.toml)
- **Docker Engine 24+** and **Docker Compose v2** (`docker compose`) — required for the containerized local stack (Milestone 3)

Optional but recommended:

- [pyenv](https://github.com/pyenv/pyenv) or [pyenv-win](https://github.com/pyenv-win/pyenv-win) to install and select Python 3.12 automatically

## Local Setup

These steps assume a fresh clone of the repository.

### 1. Clone the repository

```bash
git clone <repository-url>
cd GaiaOS
```

### 2. Verify Python 3.12

```bash
python --version
```

Expected output: `Python 3.12.x`

If you use pyenv, run `pyenv install` (reads `.python-version`) then `pyenv local 3.12` from the repo root.

### 3. Create and activate a virtual environment

**Linux / macOS:**

```bash
python -m venv .venv
source .venv/bin/activate
```

**Windows (PowerShell):**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**Windows (Command Prompt):**

```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

### 4. Upgrade pip and install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements/dev.txt
```

`requirements/dev.txt` includes `requirements/base.txt`.

### 5. Verify the environment

```bash
python --version
pip list
```

Setup is complete when the virtual environment activates without errors and `pip install -r requirements/dev.txt` finishes successfully.

## Docker Local Development

Milestone 3 establishes the containerized runtime before FastAPI is added in Milestone 4. The compose stack runs a placeholder app container and a PostgreSQL instance with PostGIS and pgvector.

### First-time or rebuild startup

```bash
docker compose up --build
```

Builds the app image and starts both services. On first boot with an empty database volume, [`infra/docker/postgres/init-extensions.sql`](infra/docker/postgres/init-extensions.sql) enables PostGIS and pgvector.

### Stop services (preserve database data)

```bash
docker compose down
```

Stops and removes containers. The named volume `postgres_data` persists, so database data survives restarts.

### Stop services and destroy database data

```bash
docker compose down -v
```

Removes containers **and volumes**. Use this after changing `init-extensions.sql` or when extensions are missing because Postgres was first initialized without the init script. **This permanently deletes local database data.**

### View logs

```bash
docker compose logs app
docker compose logs postgres
```

The app log should show settings loaded from the environment, including `database_url` pointing at `postgres:5432`. The postgres log shows startup and init script execution on first boot.

### Verify extensions

```bash
docker compose exec postgres psql -U gaiaos -d gaiaos -c "\dx"
```

Expect `postgis` and `vector` in the extension list.

### Host access to Postgres (optional)

To connect from Python on the host (venv) while Postgres runs in Docker, copy the override template:

**Linux / macOS:**

```bash
cp docker-compose.override.yml.example docker-compose.override.yml
```

**Windows (PowerShell):**

```powershell
Copy-Item docker-compose.override.yml.example docker-compose.override.yml
```

This publishes Postgres on `localhost:5432` and Redis on `localhost:6379`. Use the `DATABASE_URL` and `REDIS_URL` in `.env` (copied from `.env.example`) for host-run Python. When the app runs inside Docker Compose, `docker-compose.yml` sets them to use the service hostnames `postgres` and `redis` instead.

| Workflow | `DATABASE_URL` host | `REDIS_URL` host |
|----------|---------------------|------------------|
| App in Docker (default compose) | `postgres` | `redis` |
| Python on host, stack in Docker | `localhost` | `localhost` |

## Local Testing & Environment Setup

The application, test suite, Alembic migrations, and RQ background workers automatically load configuration from `.env` in the project root via `pydantic-settings`.

### Environment Prerequisites

1. **Copy the `.env` template**:

   **Linux / macOS:**
   ```bash
   cp .env.example .env
   cp docker-compose.override.yml.example docker-compose.override.yml
   docker compose up -d --wait postgres redis
   ```

   **Windows (PowerShell):**
   ```powershell
   Copy-Item .env.example .env
   Copy-Item docker-compose.override.yml.example docker-compose.override.yml
   docker compose up -d --wait postgres redis
   ```

   This sets up `.env` for host-run tools and publishes Postgres on `localhost:5432` and Redis on `localhost:6379`.

2. **Run migrations**:

   ```bash
   alembic upgrade head
   ```

   Alembic reads `DATABASE_URL` directly from `.env` — no manual environment exports required.

### Run the complete test suite

```bash
pytest
```

`pytest` automatically reads `DATABASE_URL` and `REDIS_URL` from `.env` via `get_settings()`.

Expected output: all tests pass (240+ tests, exact count may grow over time).

### Verify linting

**Linux / macOS**

```bash
ruff check .
```

**Windows (PowerShell)**

```powershell
ruff check .
```

### Run specific test categories

```bash
# Configuration tests only — no database required
pytest tests/test_config.py

# Redis connection and key builder tests
pytest tests/test_cache.py

# Database connectivity and extension tests
pytest tests/test_db_connection.py

# Evaluation harness and persistence tests
pytest tests/test_eval_harness.py

# Health endpoint integration tests
pytest tests/test_health.py
```

### What the tests verify

| Test file | What is tested |
|---|---|
| `test_config.py` | Settings defaults, validation, DATABASE\_URL requirement per environment |
| `test_cache.py` | RedisKeyBuilder naming, settings validation, connection lifecycle, failure path |
| `test_db_connection.py` | Real DB connectivity, PostGIS present, pgvector present |
| `test_eval_harness.py` | Evaluation suite run on empty tables, stub suite execution, database persistence |
| `test_health.py` | `/api/v1/health/live` → 200, `/api/v1/health/ready` → 200 checks (DB + Extensions + Redis) |

Configuration tests run in isolation (no database/Redis) and are always fast.
Database, Redis, and health tests require running PostgreSQL (with PostGIS and pgvector) and Redis instances.

## Continuous Integration

GitHub Actions runs the CI pipeline (`.github/workflows/ci.yml`) on every push and pull request to the `main` branch. 

The pipeline ensures:
1. The codebase is linted and formatted properly using Ruff.
2. The exact local Docker Compose architecture is spun up (Postgres + PostGIS + pgvector).
3. The complete `pytest` test suite runs successfully against the real containerized database.
4. The production Docker image is built and verified via application startup and `/api/v1/health/live` health checks.


The pipeline will fail immediately if any step fails.

## Configuration

Environment templates live in [`config/environments/`](config/environments/). For local development, copy the dev template to a `.env` file at the repo root (optional — defaults for `GAIAOS_ENV` and `LOG_LEVEL` apply without it).

### Linux / macOS

```bash
cp config/environments/dev.env.example .env
```

### Windows (PowerShell)

```powershell
Copy-Item config/environments/dev.env.example .env
```

### Windows (Command Prompt)

```cmd
copy config\environments\dev.env.example .env
```

Application code should always access configuration through `get_settings()` instead of reading environment variables directly. All configuration access is centralized in [`config/settings.py`](config/settings.py). Key settings include `LLM_MODEL` (defaults to `"gpt-4o-mini"`), `DATABASE_URL`, and `REDIS_URL`.

Load settings from anywhere in the codebase:

```python
from config import get_settings

settings = get_settings()
```

## Dependency Management

This project uses **pip + venv** (not Poetry).

| File | Purpose |
|------|---------|
| `requirements/base.txt` | Runtime dependencies |
| `requirements/dev.txt` | Development dependencies (`-r base.txt`) |

Always activate `.venv` before installing packages or running project commands.

## Contributing a Domain Agent

To add a new environmental or analytical domain agent to GaiaOS, follow the step-by-step contribution guide in [docs/CONTRIBUTING_AGENTS.md](docs/CONTRIBUTING_AGENTS.md).

Quick start CLI:
```bash
python scripts/scaffold_new_agent.py <domain_name>
python -m eval.agent_contract_validator
```

## Branching

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the branching convention: `main` plus `feature/<milestone-name>` branches.

## Tech Stack

To be implemented according to [`docs/Architecture.md`](docs/Architecture.md) across Phase 1 milestones. No application services exist yet.
