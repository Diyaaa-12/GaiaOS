# GaiaOS — Phase 1 Implementation Roadmap

**Role:** Technical Lead
**Status:** Architecture frozen (GaiaOS Architecture v1.0) — this document does not modify, question, or extend it in any way
**Scope:** Foundation only. No agents, no LangGraph, no Planner, no retrieval/RAG, no Simulation, no MCP, no Redis, no Critic, no Synthesis. Those are out of scope for Phase 1 by design.
**Execution model:** One milestone at a time, executed by Cursor. Each milestone is self-contained and leaves the repo in a working, runnable state.

---

## How to use this document

Feed Cursor one milestone at a time, in order. Do not skip ahead. Do not start Milestone N+1 until Milestone N's Acceptance Criteria are all green. This document is the only source of truth for Phase 1 scope — if something isn't listed under a milestone's Deliverables, it does not belong in Phase 1.

---

## Milestone 1 — Repository & Development Environment Setup

**Goal:** Establish the repository, version control conventions, and a reproducible local dev environment before any code is written.

**Why this milestone exists:** Every later milestone assumes a consistent repo layout, branching convention, and dependency-management approach already exist. Getting this wrong early costs the most to fix later.

**Prerequisites:** None.

**Files/Folders expected to be created:**
```
gaiaos/
├── .gitignore
├── .editorconfig
├── .python-version
├── README.md
├── CONTRIBUTING.md
├── pyproject.toml
├── requirements/
│   ├── base.txt
│   ├── dev.txt
│   └── test.txt
```

**Technologies involved:** Git, Python (version pinned via `.python-version`), `pyproject.toml`-based project metadata, pip/venv or poetry (pick one and lock it in `README.md`).

**Acceptance Criteria:**
- [ ] Repo initializes cleanly with `git init` / clone and has a documented branching convention in `CONTRIBUTING.md`
- [ ] Fresh clone + documented setup steps in `README.md` produce a working virtual environment with no errors
- [ ] `.gitignore` correctly excludes venvs, `__pycache__`, `.env`, IDE folders
- [ ] Python version is pinned and enforced

**Deliverables:** A cloneable, empty-but-installable repository with no ambiguity about how a new contributor (or Cursor, in a fresh session) sets up the environment.

**Estimated Difficulty:** Low
**Estimated Time:** 1 session

---

## Milestone 2 — Project Structure & Configuration Management

**Goal:** Lay down the full top-level folder skeleton from the frozen architecture (empty where later phases will fill in) and implement typed, environment-based configuration.

**Why this milestone exists:** The architecture document defines an exact folder structure. Establishing it now — even with empty placeholder modules — prevents structural drift later and gives every future milestone an unambiguous place to put files.

**Prerequisites:** Milestone 1

**Files/Folders expected to be created:**
```
gaiaos/
├── gateway/
│   └── __init__.py
├── orchestrator/
│   ├── __init__.py
│   ├── graph/__init__.py
│   ├── agents/__init__.py
│   └── schemas/__init__.py
├── data/
│   └── migrations/
├── infra/
├── eval/
│   ├── benchmarks/
│   ├── metrics/
│   └── harness/
├── config/
│   ├── __init__.py
│   ├── settings.py
│   └── environments/
│       ├── dev.env.example
│       ├── staging.env.example
│       └── prod.env.example
```

**Technologies involved:** Pydantic Settings (or equivalent typed-config library) for environment-based configuration loading.

**Acceptance Criteria:**
- [ ] Full folder skeleton matches the architecture document's structure exactly
- [ ] `config/settings.py` loads typed settings from environment variables with sane defaults for local dev
- [ ] Missing required env vars fail loudly at startup, not silently
- [ ] `.env.example` files exist for dev/staging/prod with placeholder (non-secret) values only
- [ ] No secrets committed anywhere in the repo

**Deliverables:** A structurally complete, empty skeleton that matches the frozen architecture, plus a working typed settings module importable from anywhere in the codebase.

**Estimated Difficulty:** Low
**Estimated Time:** 1 session

---

## Milestone 3 — Docker & Docker Compose for Local Development

**Goal:** Containerize the (currently empty) service and stand up a local Postgres instance via Docker Compose.

**Why this milestone exists:** The frozen architecture specifies Docker as the packaging unit regardless of orchestrator choice. Establishing this early means every subsequent milestone runs in the same environment it will eventually deploy in.

**Prerequisites:** Milestone 2

**Files/Folders expected to be created:**
```
gaiaos/
├── Dockerfile
├── docker-compose.yml
├── docker-compose.override.yml.example
├── .dockerignore
```

**Technologies involved:** Docker, Docker Compose, PostgreSQL image with PostGIS + pgvector extensions pre-installed (e.g. a `postgis/postgis` or `pgvector/pgvector` base image, or a custom Dockerfile layering both extensions).

**Acceptance Criteria:**
- [ ] `docker compose up` starts the app container and a Postgres container with no manual steps
- [ ] Postgres container has PostGIS and pgvector extensions available (verified via `CREATE EXTENSION` succeeding, not just image presence)
- [ ] App container builds from `Dockerfile` without errors, even though it currently has no real application logic yet
- [ ] Environment variables from Milestone 2's config flow correctly into containers

**Deliverables:** A one-command local dev environment (`docker compose up`) with a working, extension-ready Postgres instance.

**Estimated Difficulty:** Medium
**Estimated Time:** 1–2 sessions

---

## Milestone 4 — FastAPI Skeleton with Dependency Injection

**Goal:** Stand up a minimal, runnable FastAPI application with a proper dependency-injection pattern for shared resources (settings, DB session).

**Why this milestone exists:** Everything client-facing in later phases (Gateway, agent responses, SSE streaming) sits on top of this skeleton. Getting the DI pattern right now avoids retrofitting it under every future route.

**Prerequisites:** Milestone 3

**Files/Folders expected to be created:**
```
gaiaos/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── dependencies.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/__init__.py
```

**Technologies involved:** FastAPI, Uvicorn, Python dependency-injection via FastAPI's `Depends` system.

**Acceptance Criteria:**
- [ ] `uvicorn app.main:app` (or via Docker) starts without errors
- [ ] A trivial `/` or `/ping` route returns 200 with a JSON body
- [ ] Settings from Milestone 2 are injected via `Depends`, not imported as a global singleton
- [ ] API is versioned under `/api/v1` even though it currently exposes almost nothing
- [ ] OpenAPI docs (`/docs`) render correctly

**Deliverables:** A running FastAPI app, containerized, with a clean DI pattern ready for real routes.

**Estimated Difficulty:** Low–Medium
**Estimated Time:** 1–2 sessions

---

## Milestone 5 — PostgreSQL + PostGIS + pgvector: Connection Layer

**Goal:** Implement the database connection/session layer and verify both PostGIS and pgvector are usable from application code, not just from the container.

**Why this milestone exists:** The frozen architecture relies on Postgres for structured data, geospatial queries, and vector search. This milestone proves the connection layer and both extensions work end-to-end from Python before any real schema is built.

**Prerequisites:** Milestone 4

**Files/Folders expected to be created:**
```
gaiaos/
├── db/
│   ├── __init__.py
│   ├── session.py
│   ├── base.py
```

**Technologies involved:** SQLAlchemy (async), asyncpg, PostGIS, pgvector Python bindings.

**Acceptance Criteria:**
- [ ] App can open and cleanly close a DB session via the DI pattern from Milestone 4
- [ ] A test script (or startup check) confirms `CREATE EXTENSION IF NOT EXISTS postgis;` and `CREATE EXTENSION IF NOT EXISTS vector;` succeed
- [ ] A throwaway table with a `geometry` column and a throwaway table with a `vector` column can both be created and queried
- [ ] Connection pooling is configured (not one connection per request with no pool)

**Deliverables:** A verified, working async DB layer with both required extensions proven functional, independent of any real domain schema.

**Estimated Difficulty:** Medium
**Estimated Time:** 1–2 sessions

---

## Milestone 6 — Database Migrations Framework

**Goal:** Introduce a migration tool and create the first real migration(s): base schema conventions plus the extension-enabling migrations (formalizing what Milestone 5 proved ad hoc).

**Why this milestone exists:** Every later phase (domain agent tables, causal-chain tables, episodic log) needs versioned, repeatable schema changes. This must exist before any real table is added.

**Prerequisites:** Milestone 5

**Files/Folders expected to be created:**
```
gaiaos/
├── data/
│   └── migrations/
│       ├── env.py
│       ├── script.py.mako
│       └── versions/
│           └── 0001_enable_extensions.py
├── alembic.ini
```

**Technologies involved:** Alembic (or equivalent), SQLAlchemy models as the migration source of truth.

**Acceptance Criteria:**
- [ ] `alembic upgrade head` runs cleanly against the Docker Postgres instance
- [ ] `alembic downgrade base` cleanly reverses all migrations
- [ ] First migration formally enables PostGIS + pgvector extensions (idempotent, safe to re-run)
- [ ] Migration history is committed to version control and reproducible from a fresh database

**Deliverables:** A working, reversible migration pipeline with one verified migration in place.

**Estimated Difficulty:** Medium
**Estimated Time:** 1–2 sessions

---

## Milestone 7 — Basic API Gateway Layer

**Goal:** Implement the Gateway module as a thin routing + request-context layer in front of the (currently minimal) app, with stubbed auth and stubbed rate limiting — real enforcement logic deferred, but the seams in place.

**Why this milestone exists:** The frozen architecture places AuthN/Z and rate limiting at the Gateway layer, ahead of the Orchestrator. Phase 1 does not implement real auth providers or real rate-limit backends (no Redis yet), but the interception point and interfaces must exist so later phases plug in without restructuring routes.

**Prerequisites:** Milestone 4

**Files/Folders expected to be created:**
```
gaiaos/
├── gateway/
│   ├── __init__.py
│   ├── middleware.py
│   ├── auth_stub.py
│   ├── rate_limit_stub.py
```

**Technologies involved:** FastAPI middleware, request-context propagation (e.g. `contextvars`), stubbed JWT validation (no real IdP integration yet).

**Acceptance Criteria:**
- [ ] All API routes pass through Gateway middleware, verified via a request-ID header injected and visible in logs
- [ ] `auth_stub.py` defines the interface real auth will implement later, and currently allows all requests through in dev mode with a clear `TODO`/config flag marking it as a stub
- [ ] `rate_limit_stub.py` defines the interface real rate limiting will implement later (no-op in Phase 1, clearly marked)
- [ ] Stub boundaries are documented in code comments so a future milestone knows exactly where to plug in real logic without touching route definitions

**Deliverables:** A Gateway layer with the correct seams for AuthN/Z and rate limiting, non-functional by design in Phase 1 but structurally correct for later phases.

**Estimated Difficulty:** Medium
**Estimated Time:** 1–2 sessions

---

## Milestone 8 — Structured Logging Foundation

**Goal:** Implement structured, environment-aware logging across the app, gateway, and db layers.

**Why this milestone exists:** The frozen architecture's explainability and evaluation story depends on traceable execution — that starts with disciplined logging from day one, not retrofitted after agents exist.

**Prerequisites:** Milestone 7

**Files/Folders expected to be created:**
```
gaiaos/
├── logging_config/
│   ├── __init__.py
│   └── setup.py
```

**Technologies involved:** Python `structlog` (or equivalent structured logging library), JSON log formatting for non-dev environments, human-readable formatting for local dev.

**Acceptance Criteria:**
- [ ] Every request logs a structured entry including the request ID from Milestone 7's Gateway middleware
- [ ] Log level is configurable via `config/settings.py`
- [ ] Local dev logs are human-readable; a `staging`/`prod` config flag switches to JSON output
- [ ] No secrets or full request bodies are logged by default

**Deliverables:** Consistent structured logging wired through every layer built so far.

**Estimated Difficulty:** Low–Medium
**Estimated Time:** 1 session

---

## Milestone 9 — Health & Readiness Endpoints

**Goal:** Implement real health-check endpoints that verify actual dependency status (DB reachable, extensions present), not just "the process is running."

**Why this milestone exists:** Deployment (even Phase 1's local Docker setup, and later the managed container platform) needs a genuine readiness signal, and this is the natural checkpoint to prove every prior milestone's plumbing (DB, migrations, config) is actually wired together correctly.

**Prerequisites:** Milestones 6 and 8

**Files/Folders expected to be created:**
```
gaiaos/
├── app/
│   ├── api/
│   │   └── v1/
│   │       └── health.py
```

**Technologies involved:** FastAPI, DB session from Milestone 5.

**Acceptance Criteria:**
- [ ] `/api/v1/health/live` returns 200 if the process is up, with no dependency checks (liveness)
- [ ] `/api/v1/health/ready` returns 200 only if the DB is reachable and PostGIS/pgvector extensions are confirmed present; returns 503 with a clear reason otherwise (readiness)
- [ ] Both endpoints are logged via Milestone 8's structured logging
- [ ] Health check response includes a schema version / app version field

**Deliverables:** Real, dependency-aware liveness and readiness endpoints.

**Estimated Difficulty:** Low
**Estimated Time:** 1 session

---

## Milestone 10 — Testing Infrastructure & CI Setup

**Goal:** Establish the test framework, a test database strategy, and a CI pipeline that runs tests, linting, and migration checks on every push.

**Why this milestone exists:** Phase 1 closes here deliberately — no further foundation work should happen without automated verification in place, since every later phase (agents, orchestration, RAG) will be far harder to trust without this safety net already running.

**Prerequisites:** Milestone 9

**Files/Folders expected to be created:**
```
gaiaos/
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_health.py
│   ├── test_db_connection.py
│   └── test_config.py
├── .github/
│   └── workflows/
│       └── ci.yml
```

**Technologies involved:** Pytest, pytest-asyncio, a disposable test-database strategy (e.g. a dedicated test Postgres container or transactional rollback per test), GitHub Actions (or equivalent CI), a linter/formatter (e.g. ruff).

**Acceptance Criteria:**
- [ ] `pytest` runs locally and in CI against a real (containerized) test database, not mocks, for DB-touching tests
- [ ] Tests cover: health endpoints (Milestone 9), DB connection + extension presence (Milestone 5), config loading failure on missing required vars (Milestone 2)
- [ ] CI pipeline runs on every push/PR: lint, tests, and `alembic upgrade head` against a fresh test DB
- [ ] CI fails the build on any of the above failing
- [ ] README documents how to run the full suite locally in one command

**Deliverables:** A working local + CI test pipeline validating every milestone built in Phase 1, end to end.

**Estimated Difficulty:** Medium
**Estimated Time:** 2 sessions

---

## Phase 1 Dependency Graph

```
M1 (Repo & Env)
  │
M2 (Project Structure & Config)
  │
M3 (Docker & Compose)
  │
M4 (FastAPI Skeleton + DI)
  │         │
  │         └────────────┐
M5 (DB Connection Layer)  M7 (API Gateway Layer)
  │                            │
M6 (Migrations)                │
  │                            │
  └─────────────┬──────────────┘
                 │
           M8 (Logging)
                 │
           M9 (Health/Readiness)
                 │
           M10 (Testing & CI)
```

Notes on parallelism: M7 (Gateway) only depends on M4 and can be built in parallel with M5/M6 (DB layer) if working across two Cursor sessions, but both must be complete before M8. Everything else is strictly sequential.

---

## Estimated Completion Time for Phase 1

- Milestones 1–4: ~4–6 sessions (foundation + skeleton)
- Milestones 5–6: ~2–4 sessions (data layer)
- Milestones 7–9: ~3–4 sessions (gateway, logging, health)
- Milestone 10: ~2 sessions (testing/CI)

**Total Phase 1: approximately 11–16 coding sessions**, consistent with a 2–4 week part-time effort for one engineer, before any AI/agent work begins.

---

## Phase 1 Completion Checklist

- [ ] Fresh clone → documented setup → working local environment, no manual undocumented steps
- [ ] `docker compose up` brings up app + Postgres (with PostGIS + pgvector) with zero manual intervention
- [ ] FastAPI app runs, `/docs` renders, versioned API namespace in place
- [ ] DI pattern in use for settings and DB session — no global singletons
- [ ] Migrations run cleanly up and down against a fresh database
- [ ] Gateway middleware wraps every route; auth/rate-limit stub seams clearly marked for later phases
- [ ] Structured logging active across app/gateway/db layers, request-ID traceable end to end
- [ ] `/health/live` and `/health/ready` both implemented and dependency-aware
- [ ] Full test suite runs locally and in CI against a real containerized test DB
- [ ] CI blocks merges on lint/test/migration failure
- [ ] No secrets committed anywhere in the repository
- [ ] No agent, LangGraph, Planner, RAG, Simulation, MCP, Redis, Critic, or Synthesis code exists anywhere in the repo

**STOP — Phase 1 ends here. Await further instructions before beginning Phase 2.**
