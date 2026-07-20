# Causal Chain Traversal — Postgres Recursive CTE Strategy

This document details the architecture and implementation of the `CausalChainAgent` and its underlying recursive traversal strategy.

## 1. Architectural Decisions

### 1.1 Deferral of Neo4j to Phase 3 (v2)
While causal-chain reasoning is graph-shaped, the v1 knowledge base is expected to hold a small volume of records (dozens to a few thousand nodes). Under this scale constraint:
- PostgreSQL **`WITH RECURSIVE`** queries provide identical query latencies to Neo4j (under 5ms).
- Avoids the operational overhead of running, backup-planning, and securing a separate database engine (Neo4j).
- Kept the system boundaries unified inside PostgreSQL.

### 1.2 Neo4j Migration Trigger
The system should transition to Neo4j only if:
1. The historical causal graph scales beyond **50,000 nodes** or **100,000 edges**.
2. We require complex pattern-matching graph queries (e.g. "Find all triads of event types occurring within N days regardless of path sequence") that recursive SQL queries cannot express cleanly.

---

## 2. Recursive CTE Implementation

All graph traversals are handled by a single query in [causal_repository.py](file:///c:/Users/DIYA/OneDrive/Documents/Projects/GaiaOS/db/causal_repository.py):

```sql
WITH RECURSIVE causal_path AS (
    -- 1. Anchor Member: Locate starting event
    SELECT
        he.id AS event_id,
        he.event_type,
        he.region,
        he.details,
        ARRAY[he.id] AS path_ids,
        ARRAY[he.event_type] AS path_types,
        1 AS depth,
        ARRAY[]::numeric[] AS edge_confidences
    FROM hazard_events he
    WHERE he.event_type = :event_type AND he.region = :region

    UNION ALL

    -- 2. Recursive Member: Traverse relations
    SELECT
        child.id AS event_id,
        child.event_type,
        child.region,
        child.details,
        cp.path_ids || child.id AS path_ids,
        cp.path_types || child.event_type AS path_types,
        cp.depth + 1 AS depth,
        cp.edge_confidences || hr.confidence AS edge_confidences
    FROM causal_path cp
    JOIN hazard_relationships hr ON cp.event_id = hr.parent_id
    JOIN hazard_events child ON hr.child_id = child.id
    WHERE cp.depth < :max_depth
      AND NOT (child.id = ANY(cp.path_ids)) -- Cycle prevention guard
)
SELECT event_id, event_type, region, details, path_ids, path_types, depth, edge_confidences
FROM causal_path
ORDER BY depth ASC;
```

### 2.1 Cycle Prevention Guard
Infinite recursion is prevented by adding `AND NOT (child.id = ANY(cp.path_ids))` to the JOIN condition. This checks if the node we are about to visit is already in the accumulated path array (`path_ids`), terminating that branch immediately if a loop is detected.

### 2.2 Depth Bounding
To guarantee the query terminates quickly and respects configurable boundaries, we enforce `cp.depth < :max_depth` (defaulting to 4 hops).

---

## 3. Explanations and Scoring

### 3.1 Explainability and Traversal Path
The SELECT statement returns `path_ids` (visited UUIDs) and `path_types` (human-readable string chain). We package these in `Evidence.extra_metadata` to improve traceability and ensure downstream consumers can explain why a given chain was matched.

### 3.2 Chain Confidence Helper
Instead of hardcoding the confidence calculation directly in the SQL engine, the query returns the list of edge confidences `edge_confidences`. The confidence value is calculated in Python via:

```python
def calculate_chain_confidence(edge_confidences: list[float]) -> float:
    if not edge_confidences:
        return 1.0
    return min(edge_confidences)
```

This makes it easy to replace this logic later with a weighted average, decay function, or joint probability distribution.

---

## 4. Query Protection (Statement Timeout)

To protect the system from long-running or runaway recursive queries, we set a transaction-local timeout prior to executing the SQL query:

```python
await session.execute(text("SET LOCAL statement_timeout = 2000;"))
```

If query execution exceeds 2000ms, PostgreSQL cancels the query, raising a `57014` exception which the repository maps to a Python `TimeoutError`. The agent catches this, logs it, and returns an `errors` list instead of failing the graph execution.
