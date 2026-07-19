# Agent Interface Contract Specification

Every domain agent in GaiaOS (including Air Quality, Seismic, Ocean, Atmosphere, Wildfire, and Causal agents) must conform to a standardized, typed input/output contract. This prevents code fragmentation and enables the Adaptive Planner and Synthesis engines to interact with all domain nodes in a uniform manner.

---

## 1. Data Schema Contracts

The contracts are defined in [agent_io.py](file:///c:/Users/DIYA/OneDrive/Documents/Projects/GaiaOS/orchestrator/schemas/agent_io.py) and [complexity.py](file:///c:/Users/DIYA/OneDrive/Documents/Projects/GaiaOS/orchestrator/schemas/complexity.py).

### Evidence

Represents a single granular factual block of information retrieved by a domain tool.
- `source` (str): Unique identifier or URL of the data provider (e.g. `OpenAQ API (Station: Paris-Centre)`).
- `claim` (str): The factual observation statement.
- `confidence` (float): A value between `0.0` and `1.0` indicating evidence certainty.
- `retrieved_at` (datetime): Timestamp (UTC) when the source was queried.

### AgentInput

The input arguments supplied to the domain agent's `run()` function.
- `investigation_id` (UUID): Unique ID tracking the active session.
- `query` (str): The user query text.
- `region_hint` (str | None): Extracted target location boundary.

### AgentOutput

The return type envelope returned by the agent.
- `agent_name` (str): Identifier of the executing agent (e.g. `air_quality`).
- `evidence` (list[Evidence]): Collected facts list.
- `errors` (list[str]): Non-blocking tool querying error strings.

---

## 2. Implementing a Domain Agent

To implement a new domain agent:

1. Create the package directory structure inside `orchestrator/agents/<domain>/`.
2. Implement the `async def run(agent_input: AgentInput) -> AgentOutput` entrypoint.
3. Keep tool failures non-blocking: do not raise exceptions inside the graph nodes. Instead, capture API errors as string items inside `AgentOutput.errors` and proceed with an empty or partial list of `evidence` items. This ensures the orchestrator can synthesize partial reports rather than crashing.

### Reference Code Blueprint

```python
from orchestrator.schemas.agent_io import AgentInput, AgentOutput, Evidence

async def run(agent_input: AgentInput) -> AgentOutput:
    evidence = []
    errors = []
    
    try:
        # Call third-party APIs or execute tools
        data = await call_domain_tool(agent_input.region_hint)
        evidence.append(
            Evidence(
                source="Domain API",
                claim=f"Measurements read: {data}",
                confidence=0.9,
            )
        )
    except Exception as err:
        errors.append(f"Query failed: {str(err)}")
        
    return AgentOutput(
        agent_name="my_domain",
        evidence=evidence,
        errors=errors
    )
```
