# GaiaOS

An Agentic Planetary Risk Intelligence Platform.

## Status

Phase 1 — Foundation (in progress)

| Milestone | Status |
|-----------|--------|
| Milestone 1 — Repository & Development Environment Setup | Complete |
| Milestone 2 — Project Structure & Configuration | Complete |
| Milestone 3 — Docker & Docker Compose | Not started |

Architecture is frozen in [`docs/Architecture.md`](docs/Architecture.md). Phase 1 scope and ordering are defined in [`docs/Roadmap_Phase1.md`](docs/Roadmap_Phase1.md).

## Prerequisites

- **Git**
- **Python 3.12** — version pinned in [`.python-version`](.python-version) and [`pyproject.toml`](pyproject.toml)

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

## Configuration

Environment templates live in [`config/environments/`](config/environments/). For local development, copy the dev template to a `.env` file at the repo root (optional — defaults for `GAIAOS_ENV` and `LOG_LEVEL` apply without it):

```bash
cp config/environments/dev.env.example .env
```

Application code should always access configuration through `get_settings()` instead of reading environment variables directly. All configuration access is centralized in [`config/settings.py`](config/settings.py).

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
