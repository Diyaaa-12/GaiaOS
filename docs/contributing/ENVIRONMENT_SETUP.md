# Development Environment Setup Guide

[Documentation Hub](../README.md) | [First PR Guide](FIRST_PR.md) | [Project Structure](PROJECT_STRUCTURE.md) | [Development Workflow](DEVELOPMENT_WORKFLOW.md)

---

This guide provides concise instructions for configuring your local GaiaOS development environment across **Windows**, **Linux**, and **macOS**, highlighting OS-specific setup pitfalls, common setup problems, and frequently asked questions.

---

## 📋 Prerequisites

| Tool | Required Version | Purpose |
|------|------------------|---------|
| **Python** | `3.12.x` (pinned in `.python-version`) | Primary backend runtime |
| **Docker Engine & Compose** | `24.0+` / `v2.20+` | PostgreSQL (PostGIS), Redis, and service containerization |
| **Git** | `2.30+` | Source control |
| **Node.js & npm** *(Optional)* | `18+` / `9+` | Admin UI dashboard development (`admin_ui/`) |

---

## 🛠️ Step-by-Step Environment Setup

### 1. Clone the Repository
```bash
git clone https://github.com/Diyaaa-12/GaiaOS.git
cd GaiaOS
```

### 2. Create and Activate Virtual Environment

- **Linux / macOS**:
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```

- **Windows (PowerShell)**:
  ```powershell
  python -m venv .venv
  .\.venv\Scripts\Activate.ps1
  ```

> [!TIP]
> **Windows Execution Policy Pitfall**: If PowerShell throws `cannot be loaded because running scripts is disabled on this system`, run:
> ```powershell
> Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
> ```

### 3. Install Pinned Dependencies
Install exact development dependencies from the lockfile:
```bash
pip install -r requirements/dev.lock
```

### 4. Configure Local Environment Variables
Copy template environment files:
```bash
# Copy main environment variables
cp .env.example .env

# Copy Docker compose local override configuration
cp docker-compose.override.yml.example docker-compose.override.yml
```

### 5. Start Infrastructure Services
Spin up PostgreSQL (with PostGIS and pgvector) and Redis using Docker Compose:
```bash
docker compose up -d postgres redis
```

Verify service status:
```bash
docker compose ps
```

---

## 🖥️ OS-Specific Setup & Pitfalls

### Windows Setup Notes
- **Line Endings (CRLF vs LF)**: Git on Windows may convert line endings to `CRLF`, causing shell scripts or Docker build checks to fail. Set line ending behavior before cloning:
  ```cmd
  git config --global core.autocrlf input
  ```
- **Docker Desktop & WSL 2**: Ensure Docker Desktop is configured to use the **WSL 2 backend** (Settings -> General -> Use the WSL 2 based engine).
- **PowerShell Execution Policy**: Virtual environment activation scripts (`Activate.ps1`) require execution privileges per process session (see Step 2 above).

### Linux (Ubuntu / Debian) Setup Notes
- **System Headers**: Building binary packages (e.g. `psycopg2`, `shapely`) requires C build utilities and PostgreSQL development headers:
  ```bash
  sudo apt-get update
  sudo apt-get install -y build-essential libpq-dev python3-dev
  ```
- **Docker Group Privileges**: Run Docker commands without `sudo` by adding your user to the `docker` group:
  ```bash
  sudo usermod -aG docker $USER
  newgrp docker
  ```

### macOS (Apple Silicon / Intel) Setup Notes
- **Homebrew Dependencies**: Install `libpq` for PostgreSQL client libraries:
  ```bash
  brew install libpq
  ```
- **Architecture Wheels**: Ensure Python 3.12 is compiled natively for `arm64` (Apple Silicon M1/M2/M3) to prevent emulation overhead during type checking and test execution.

---

## ❓ Common Setup Problems & Troubleshooting

### Problem 1: Port Binding Conflict (5432, 6379, 8000, 3000)
- **Symptom**: `Error starting userland proxy: listen tcp4 0.0.0.0:5432: bind: address already in use`
- **Cause**: A local instance of PostgreSQL, Redis, or Uvicorn is already running on your host machine.
- **Resolution**: Either stop the host service (`sudo systemctl stop postgresql`) or edit `docker-compose.override.yml` to map host ports to alternative numbers (e.g., `5433:5432`).

### Problem 2: Database Connection Failures during Tests
- **Symptom**: `psycopg2.OperationalError: could not connect to server: Connection refused`
- **Cause**: PostgreSQL container hasn't finished initialization or health check.
- **Resolution**: Wait 5 seconds after starting containers or inspect container logs:
  ```bash
  docker compose logs postgres
  ```

### Problem 3: Alembic Migration State Out of Sync
- **Symptom**: `alembic.util.exc.CommandError: Can't locate revision identified by '...'`
- **Cause**: Local database schema has stale migration markers.
- **Resolution**: Apply fresh migrations to head:
  ```bash
  alembic upgrade head
  ```
  Or reset database state completely:
  ```bash
  docker compose down -v
  docker compose up -d postgres redis
  alembic upgrade head
  ```

---

## 🙋 Frequently Asked Questions (FAQ)

#### Q1: Do I need Docker running to execute pure unit tests?
**A**: No. Pure unit tests (such as domain agent unit tests or utility function tests) run directly in your Python environment without Docker:
```bash
pytest tests/test_seismic_agent.py
```
However, integration tests that interact with PostgreSQL or Redis require running container services.

#### Q2: How do I verify my setup matches CI requirements before creating a PR?
**A**: Run the local verification script:
```bash
python scripts/verify.py
```
This runs `ruff`, `mypy`, `pytest`, and checks OpenAPI spec synchronization in a single pass.

#### Q3: Why is my PR failing the "Verify OpenAPI specification drift" CI step?
**A**: You updated a FastAPI route signature or Pydantic request/response model without re-generating the public OpenAPI specification file (`docs/api/openapi/openapi.json`). Fix it by running:
```bash
python scripts/generate_openapi_spec.py
git add docs/api/openapi/openapi.json
git commit -m "docs: update openapi specification"
```
