# GaiaOS

[![CI](https://github.com/Diyaaa-12/GaiaOS/actions/workflows/ci.yml/badge.svg)](https://github.com/Diyaaa-12/GaiaOS/actions/workflows/ci.yml)

An Agentic Planetary Risk Intelligence Platform.

## Status

Phase 1 — Foundation (Complete)

| Milestone | Status |
|-----------|--------|
| Milestone 1 — Repository & Development Environment Setup | Complete |
| Milestone 2 — Project Structure & Configuration | Complete |
| Milestone 3 — Docker & Docker Compose | Complete |
| Milestone 4 — FastAPI Foundation & Request ID | Complete |
| Milestone 5 — PostgreSQL Database Architecture | Complete |
| Milestone 6 — Alembic Migration Pipeline | Complete |
| Milestone 7 — Gateway Middleware & Logging | Complete |
| Milestone 8 — Production Environment Settings | Complete |
| Milestone 9 — Application Health Probes | Complete |
| Milestone 10 — Test Infrastructure & GitHub Actions CI | Complete |

Architecture is frozen in [`docs/Architecture.md`](docs/Architecture.md). Phase 1 scope and ordering are defined in [`docs/Roadmap_Phase1.md`](docs/Roadmap_Phase1.md).

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

This publishes Postgres on `localhost:5432` and Redis on `localhost:6379`. Use the `DATABASE_URL` and `REDIS_URL` in [`config/environments/dev.env.example`](config/environments/dev.env.example) for host-run Python. When the app runs inside Docker Compose, `docker-compose.yml` sets them to use the service hostnames `postgres` and `redis` instead.

| Workflow | `DATABASE_URL` host | `REDIS_URL` host |
|----------|---------------------|------------------|
| App in Docker (default compose) | `postgres` | `redis` |
| Python on host, stack in Docker | `localhost` | `localhost` |

## Local Testing

The test suite runs against real PostgreSQL and Redis instances — no mocks for integration tests. Configuration tests run without external dependencies.

### Prerequisites

1. **Docker Compose stack must be running** with Postgres exposed on `localhost:5432` and Redis on `localhost:6379`.
   The ports are not exposed by default. Create the override file once:

   **Linux / macOS:**
   ```bash
   cp docker-compose.override.yml.example docker-compose.override.yml
   docker compose up -d --wait postgres redis
   ```

   **Windows (PowerShell):**
   ```powershell
   Copy-Item docker-compose.override.yml.example docker-compose.override.yml
   docker compose up -d --wait postgres redis
   ```

   This publishes Postgres on `localhost:5432` and Redis on `localhost:6379`.

2. **Run migrations** to initialize the database schema:

   **Linux / macOS:**
   ```bash
   DATABASE_URL=postgresql://gaiaos:gaiaos_dev_password@localhost:5432/gaiaos alembic upgrade head
   ```

   **Windows (PowerShell):**
   ```powershell
   $env:DATABASE_URL = "postgresql://gaiaos:gaiaos_dev_password@localhost:5432/gaiaos"
   alembic upgrade head
   ```

3. **`DATABASE_URL` and `REDIS_URL` must be set** in the terminal where you run pytest.

### Run the complete test suite

**Linux / macOS:**
```bash
DATABASE_URL=postgresql://gaiaos:gaiaos_dev_password@localhost:5432/gaiaos REDIS_URL=redis://localhost:6379/0 pytest
```

**Windows (PowerShell):**
```powershell
$env:DATABASE_URL = "postgresql://gaiaos:gaiaos_dev_password@localhost:5432/gaiaos"
$env:REDIS_URL = "redis://localhost:6379/0"
pytest
```

Expected output: all tests pass (`53 passed`).

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

## Branching

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the branching convention: `main` plus `feature/<milestone-name>` branches.

## Tech Stack

To be implemented according to [`docs/Architecture.md`](docs/Architecture.md) across Phase 1 milestones. No application services exist yet.
