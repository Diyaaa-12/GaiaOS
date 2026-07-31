# Contributing a Domain Agent to GaiaOS

This guide provides step-by-step instructions for adding a new environmental or analytical domain agent to GaiaOS. The framework enforces a standardized contract (`AgentInput -> AgentOutput`) and benchmark test coverage to guarantee system stability and evaluation reproducibility.

---

## 1. Architectural Principles

- **First-Party vs. Plugin Agents**:
  - **First-Party Agents** (this guide): Core agents maintained in the `orchestrator/agents/` repository tree via Pull Request.
  - **Plugin Agents**: Independently distributed Python packages (`pip install`) discovered dynamically via entry points. For developing external plugins, see [PLUGIN_DEVELOPMENT.md](file:///c:/Users/DIYA/OneDrive/Documents/Projects/GaiaOS/docs/PLUGIN_DEVELOPMENT.md).
- **Standard I/O Contract**: All domain agents implement a single entry point:
  ```python
  async def run(agent_input: AgentInput, bus: CollaborationBus | None = None) -> AgentOutput: ...
  ```
- **Explicit Registry**: First-party agents are statically registered in `orchestrator/agents/registry.py`. Dynamic plugin agents are discovered at worker startup via package entry points.
- **Zero Runtime Redesign**: Adding an agent requires zero changes to the orchestrator graph or runtime core.

---

## 2. Step-by-Step Contribution Workflow

### Step 1: Scaffold the New Agent
Run the scaffolding script with your target domain name (e.g. `hydrology`):

```bash
python scripts/scaffold_new_agent.py hydrology
```

This creates:
- Package directory: `orchestrator/agents/hydrology/`
- Implementation: `orchestrator/agents/hydrology/agent.py`
- Test suite: `tests/test_hydrology_agent.py`

### Step 2: Implement Domain Logic (`agent.py`)
In `orchestrator/agents/<domain_name>/agent.py`, implement your data retrieval, API tool calls, and evidence extraction logic:

```python
async def run(agent_input: AgentInput) -> AgentOutput:
    evidence_list: list[Evidence] = []
    errors: list[str] = []

    try:
        # 1. Parse region or query parameters
        # 2. Call domain tool client (e.g. tools/hydrology/client.py)
        # 3. Construct Evidence items
        evidence_list.append(
            Evidence(
                source="Hydrology API",
                claim="Observed river discharge rate of 45 m3/s at Gauge station 102.",
                confidence=0.95,
                retrieved_at=datetime.now(UTC),
            )
        )
    except Exception as exc:
        errors.append(f"Failed to query hydrology source: {exc}")

    return AgentOutput(
        agent_name="hydrology",
        evidence=evidence_list,
        errors=errors,
    )
```

### Step 3: Register Agent in `registry.py`
Open `orchestrator/agents/registry.py` and register your new agent in `register_agents()`:

```python
from orchestrator.agents.hydrology.agent import run as run_hydrology

agent_registry.register("hydrology", run_hydrology)
```

### Step 4: Add Unit Tests (`tests/test_<domain_name>_agent.py`)
Ensure your agent includes unit tests mocking external HTTP calls or testing query parsing logic:

```bash
pytest tests/test_hydrology_agent.py
```

### Step 5: Add Evaluation Benchmark Questions (`eval/benchmarks/questions.json`)
Every registered agent **must** have benchmark test coverage in the evaluation dataset. Open `eval/benchmarks/questions.json` and add at least one question specifying your domain:

```json
{
  "id": "hydrology_river_discharge",
  "question_text": "What is the recent river discharge rate and water level near the Danube basin?",
  "expected_domains": ["hydrology"],
  "expected_complexity": "moderate",
  "reference_answer": "Danube discharge rate measured at 45 m3/s.",
  "reference_evidence": {
    "source": "Hydrology API"
  }
}
```

### Step 6: (Optional) Configure Settings (`config/settings.py`)
If your agent requires an external API key or custom URL endpoint, add typed settings to `config/settings.py` using `pydantic.Field`:

```python
hydrology_api_url: str = Field(
    default="https://api.hydrology.example/v1",
    validation_alias="HYDROLOGY_API_URL",
    description="Hydrology observation API endpoint.",
)
```

### Step 7: Validate Agent Contracts & Coverage
Run the contract validator to confirm your agent signature and benchmark coverage satisfy all CI checks:

```bash
python -m eval.agent_contract_validator
```

---

## 3. Contribution Verification Checklist

Before submitting a pull request, ensure all checklist items pass:

- [ ] Scaffolded agent package created under `orchestrator/agents/<domain_name>/`.
- [ ] Entry point `async def run(agent_input: AgentInput) -> AgentOutput` implemented.
- [ ] Registered in `orchestrator/agents/registry.py`.
- [ ] Unit test suite added in `tests/test_<domain_name>_agent.py`.
- [ ] At least one question added to `eval/benchmarks/questions.json` with `expected_domains` matching `<domain_name>`.
- [ ] `python -m eval.agent_contract_validator` succeeds with 0 errors.
- [ ] `ruff check .`, `mypy .`, and `pytest` pass cleanly.
