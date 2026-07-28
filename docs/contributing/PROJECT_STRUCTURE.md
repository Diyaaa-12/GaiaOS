# Repository Structure & Code Placement Guide

[Documentation Hub](../README.md) | [Environment Setup](ENVIRONMENT_SETUP.md) | [First PR Guide](FIRST_PR.md) | [How-To Guides](HOW_TO_GUIDES.md)

---

This document provides a complete directory map of the GaiaOS repository and a decision matrix answering the question: **"Where should I add new code?"**

> [!NOTE]
> For high-level system concepts, layer interactions, and architectural philosophy, refer to the main [System Architecture Specification](../Architecture.md).

---

## 📂 Repository Directory Layout Map

```text
GaiaOS/
├── .github/                  # GitHub Actions CI workflows, issue & PR templates, label definitions
├── .vscode/                  # Workspace extension recommendations and debug launch configurations
├── admin_ui/                 # React / TypeScript operational dashboard & metrics interface
├── alembic/                  # Alembic database migration scripts and environment config
│   └── versions/             # Reversible SQL schema migration scripts
├── alerting/                 # Alert rule evaluations and notification triggers
├── app/                      # Core FastAPI REST & SSE application server
│   ├── api/v1/               # Version 1 API routing and endpoint handlers
│   │   ├── endpoints/        # Resource-specific endpoint logic (risk, agents, health, etc.)
│   │   └── router.py         # Primary v1 API router aggregation
│   ├── core/                 # App lifecycle, exception handlers, and global middleware
│   └── main.py               # FastAPI application initialization & factory
├── auth/                     # JWT authentication, API key validation, and permission checks
├── cache/                    # Redis caching layer and key-value helpers
├── config/                   # Typed environment configurations (Pydantic BaseSettings)
├── data/                     # Sample datasets, seed files, and geospatial fixtures
├── db/                       # SQLAlchemy database models, engine session, and base classes
│   └── models/               # Declarative SQLAlchemy models (User, RiskAssessment, Evidence, etc.)
├── docs/                     # Documentation hub, architectural specs, API specs, and contributor guides
│   ├── api/                  # OpenAPI JSON specifications and API changelogs
│   ├── audits/               # Historical audit reports and single source of truth matrix
│   ├── contributing/         # Detailed developer guides (Environment, Structure, Guides, First PR)
│   └── releases/             # Versioning and release governance documents
├── eval/                     # Agent evaluation suite, contract validator, and benchmarks
│   └── benchmarks/           # Question datasets for testing domain agents
├── gateway/                  # Gateway middleware, rate limiting, and request routing
├── ingestion/                # Data ingestion pipelines and external hazard feeds
├── logging_config/           # Structured JSON logging configuration
├── mcp_servers/              # Model Context Protocol (MCP) server implementations
├── metrics/                  # Prometheus metrics collectors and telemetry counters
├── ops/                      # Operational runbooks, backup scripts, and deployment configurations
│   └── runbooks/             # Standard operating procedure (SOP) Markdown runbooks
├── orchestrator/             # Multi-agent reasoning core (LangGraph workflow engine)
│   ├── agents/               # Domain-specific analytical risk agents
│   │   ├── atmosphere/       # Atmospheric risk agent implementation
│   │   ├── seismic/          # Seismic risk agent implementation
│   │   ├── registry.py       # Explicit domain agent registry
│   │   └── base.py           # Standard agent I/O contract definitions
│   └── graph.py              # LangGraph execution graph definition
├── requirements/             # Pinned dependency requirements and dev.lock lockfile
├── scripts/                  # Developer CLI tools (verify.py, generate_openapi_spec.py, scaffold_new_agent.py)
├── simulation_engine/        # Risk simulation and scenario modeling engines
├── tests/                    # Pytest test suite (unit, integration, e2e)
├── tools/                    # Domain-specific tool clients and external API integrations
└── workers/                  # RQ background task worker definitions and queuing logic
```

---

## 🗺️ "Where Should I Add New Code?"

Use this reference table to determine the exact location for new files and features:

| Goal / Requirement | Primary Directory | Files to Modify / Create |
|--------------------|-------------------|--------------------------|
| **Add a new Domain Agent** | `orchestrator/agents/<domain>/` | 1. Create `orchestrator/agents/<domain>/agent.py`<br>2. Register in `orchestrator/agents/registry.py`<br>3. Add test in `tests/test_<domain>_agent.py`<br>4. Add question to `eval/benchmarks/questions.json` |
| **Add an API Endpoint** | `app/api/v1/endpoints/` | 1. Add endpoint handler in `app/api/v1/endpoints/<feature>.py`<br>2. Register router in `app/api/v1/router.py`<br>3. Add test in `tests/test_api_<feature>.py`<br>4. Run `python scripts/generate_openapi_spec.py` |
| **Add a Database Model** | `db/models/` | 1. Add model file in `db/models/<entity>.py`<br>2. Export model in `db/models/__init__.py`<br>3. Generate migration: `alembic revision --autogenerate -m "add <entity>"`<br>4. Apply migration: `alembic upgrade head` |
| **Add a Background Task** | `workers/tasks/` | 1. Define task function in `workers/tasks/<task_name>.py`<br>2. Export task in worker registry<br>3. Add test in `tests/test_worker_<task_name>.py` |
| **Add External Tool Client** | `tools/<tool_name>/` | 1. Implement tool client in `tools/<tool_name>/client.py`<br>2. Export client interfaces<br>3. Add unit tests mocking HTTP calls in `tests/` |
| **Add Configuration Setting** | `config/settings.py` | 1. Add field to `Settings` class using `pydantic.Field`<br>2. Update `.env.example` with default value |
| **Add Integration / Unit Tests** | `tests/` | Add test file matching `tests/test_<feature>.py` |
| **Add Developer CLI Script** | `scripts/` | Add utility script in `scripts/<utility_name>.py` |
