# Step-by-Step Contributor How-To Guides

[Documentation Hub](../README.md) | [Environment Setup](ENVIRONMENT_SETUP.md) | [First PR Guide](FIRST_PR.md) | [Development Workflow](DEVELOPMENT_WORKFLOW.md)

---

This document provides step-by-step procedural guides for common development tasks in GaiaOS.

---

## 1. How to Add a New Domain Agent

Adding a new domain-specific analytical agent (e.g. `hydrology`, `volcanic`, `wildfire`) follows a standardized contract framework.

### Steps:
1. **Scaffold the Agent Package**:
   ```bash
   python scripts/scaffold_new_agent.py <domain_name>
   ```
   This generates:
   - `orchestrator/agents/<domain_name>/agent.py`
   - `orchestrator/agents/<domain_name>/__init__.py`
   - `tests/test_<domain_name>_agent.py`

2. **Implement Agent Logic (`agent.py`)**:
   Ensure your agent implements the standard signature:
   ```python
   async def run(agent_input: AgentInput) -> AgentOutput:
       # Retrieve data using tool clients (e.g. tools/<domain>/client.py)
       # Return typed AgentOutput containing Evidence items and errors
   ```

3. **Register Agent in `registry.py`**:
   Open `orchestrator/agents/registry.py` and register the runner:
   ```python
   from orchestrator.agents.<domain_name>.agent import run as run_<domain_name>
   agent_registry.register("<domain_name>", run_<domain_name>)
   ```

4. **Add Benchmark Test Questions**:
   Open `eval/benchmarks/questions.json` and add at least one question specifying `"expected_domains": ["<domain_name>"]`.

5. **Validate Agent Contract**:
   Run the contract validation suite:
   ```bash
   python -m eval.agent_contract_validator
   ```

> [!NOTE]
> For complete contract details, see the dedicated [Domain Agent Contribution Guide](../CONTRIBUTING_AGENTS.md).

---

## 2. How to Add an API Endpoint

Adding a new REST or SSE endpoint to the GaiaOS public API.

### Steps:
1. **Define Pydantic Schemas**:
   Create request and response schemas in `app/api/v1/endpoints/` (or update existing schema files).

2. **Create Endpoint Handler**:
   In `app/api/v1/endpoints/<feature>.py`, implement the FastAPI route:
   ```python
   from fastapi import APIRouter, Depends, HTTPException, status
   
   router = APIRouter()
   
   @router.get("/my-feature", response_model=MyFeatureResponse)
   async def get_my_feature():
       return MyFeatureResponse(status="active")
   ```

3. **Register Router in v1 Aggregator**:
   Open `app/api/v1/router.py` and include your router:
   ```python
   from app.api.v1.endpoints import my_feature
   api_router.include_router(my_feature.router, prefix="/my-feature", tags=["My Feature"])
   ```

4. **Write Endpoint Tests**:
   Add test coverage in `tests/test_api_my_feature.py` using FastAPI's `TestClient` or `AsyncClient`.

5. **Update OpenAPI Specification**:
   Regenerate the OpenAPI JSON spec to reflect your new endpoint:
   ```bash
   python scripts/generate_openapi_spec.py
   git add docs/api/openapi/openapi.json
   ```

---

## 3. How to Add a DB Model & Alembic Migration

Adding a new PostgreSQL database table or modifying column definitions using SQLAlchemy 2.0 and Alembic.

### Steps:
1. **Define SQLAlchemy Model**:
   Create a new model class in `db/models/<entity>.py` inheriting from `Base`:
   ```python
   from sqlalchemy import String, DateTime
   from sqlalchemy.orm import Mapped, mapped_column
   from db.base import Base

   class CustomEntity(Base):
       __tablename__ = "custom_entities"

       id: Mapped[str] = mapped_column(String, primary_key=True)
       name: Mapped[str] = mapped_column(String, nullable=False)
   ```

2. **Export Model in Package `__init__.py`**:
   Add your model import to `db/models/__init__.py` so Alembic auto-detects it.

3. **Generate Alembic Migration**:
   ```bash
   alembic revision --autogenerate -m "add custom_entities table"
   ```
   Inspect the generated script in `alembic/versions/` to verify operations.

4. **Apply Migration Locally**:
   ```bash
   alembic upgrade head
   ```

5. **Add Model Tests**:
   Add unit tests in `tests/` validating CRUD operations against the database session fixture.

---

## 4. How to Write and Run Tests

GaiaOS uses `pytest` with `pytest-asyncio` configured in `asyncio_mode = "auto"`.

### Test Placement:
- All tests reside in `tests/` and must start with `test_`.
- Unit tests for agents: `tests/test_<domain>_agent.py`.
- API endpoint tests: `tests/test_api_<endpoint>.py`.
- Task worker tests: `tests/test_worker_<task>.py`.

### Test Conventions & Fixtures (`tests/conftest.py`):
- Use predefined fixtures from `conftest.py` (e.g. `db_session`, `test_client`, `mock_redis`).
- Avoid hardcoding localhost URLs or real production API keys; mock external HTTP endpoints using `unittest.mock` or `httpx.HTTPTransport`.

### Running Tests:
```bash
# Run all tests
pytest

# Run a specific test file
pytest tests/test_health.py

# Run a specific test function
pytest tests/test_health.py -k test_live_health_endpoint
```

---

## 5. How to Update the OpenAPI Specification

GaiaOS maintains a deterministic OpenAPI 3.1.0 specification stored at `docs/api/openapi/openapi.json`.

### Steps:
1. **Regenerate Spec File**:
   ```bash
   python scripts/generate_openapi_spec.py
   ```
2. **Check Spec Diff**:
   ```bash
   git diff docs/api/openapi/openapi.json
   ```
3. **Commit Updated Spec**:
   If routes, response models, or docstrings changed, stage and commit the updated `openapi.json` file along with your code changes.

