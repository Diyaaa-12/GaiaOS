# Adaptive Planner — Query Complexity Taxonomy

This document describes the classification taxonomy used by the Supervisor agent to categorize user queries into Complexity Tiers and target specific environmental domains.

---

## 1. Complexity Tier Definitions

To optimize API cost, processing latency, and execution reliability, queries are divided into three tiers:

### Trivial (`trivial`)
- **Criteria**: Query requests current environmental metrics for a **single variable or location**, requiring no sequential reasoning, historical simulation, or cross-domain correlation.
- **Example**: *"What is the current air quality in London?"*
- **Current Behavior (Milestone 3)**: Routes directly to the single matched domain agent (Air Quality).

### Moderate (`moderate`)
- **Criteria**: Query asks about **multiple variables** or covers multiple domain boundaries, but does not involve predictive modeling or causal sequences.
- **Example**: *"Show me the current ocean temperature and seismic activity near Tokyo."*
- **Current Behavior (Milestone 3)**: Routes to the `fan_out` placeholder node (which executes the Air Quality agent as its sole active target).
- **Future Behavior (Milestone 4)**: Will route to the parallel `FanOutCoordinator` executing matched domain agents concurrently.

### Complex (`complex`)
- **Criteria**: Query requires **simulation, predictive forecasting, causal tracing**, or historical analysis crossing multiple timeframes.
- **Example**: *"Predict if a seismic event will trigger a coastal flood near Madrid, and model the plume dispersion."*
- **Current Behavior (Milestone 3)**: Routes to the `fan_out` placeholder node (executing the Air Quality agent as its sole active target).
- **Future Behavior (Milestone 4+)**: Will route to the parallel `FanOutCoordinator`, gate downstream critic/verification steps (Milestone 7), and trigger simulation forecast engines (Milestone 8).

---

## 2. Decision Logic and Priority Overrides

To ensure user safety and query coverage, the planner prioritizes complexity over simplicity:
1. **Fallback Default**: If query classification fails or times out, the planner defaults to `moderate` rather than silently downgrading to a `trivial` query path.
2. **Ambiguity Overrides**: If a query has mixed characteristics (e.g. mentions trivial variables but requests a prediction), the planner routes to the highest matched tier (e.g. `complex`).

---

## 3. Classifier Heuristics (Regex & Keywords)

- **Complex Triggers**: `predict`, `forecast`, `simulation`, `causal`, `trigger`, `affect`, `tsunami`, `historical modeling`.
- **Moderate Triggers**: `seismic`, `ocean`, `atmosphere`, `wildfire`, or matching multiple domain scopes.
- **Trivial Triggers**: `air quality`, `pm2.5`, `pm10`, `aqi`, `current`.
