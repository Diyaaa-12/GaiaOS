# GaiaOS — Phase 2 Architecture & Implementation Roadmap

**Role:** Principal Software Architect
**Status:** Phase 1 complete and frozen — not revisited below except where a Phase 1 artifact is a direct dependency of a Phase 2 milestone (called out explicitly, never modified).
**Source of truth:** `docs/Architecture.md` (GaiaOS Architecture v1.0). Nothing in this document overrides a technology or component decision made there. This document sequences and details *how Phase 2 gets built*, not *what gets built* — that was already decided.

---

## 0. Pre-Flight: Hidden-Dependency Analysis

Before laying out milestones, I traced every Phase 2 component backward to find anything that would surface mid-build as "we should have built this two milestones ago." Four real ones surfaced. All four are resolved by re-sequencing, not by changing any frozen decision.

**1. Redis has no Phase 1 milestone, but the very first LangGraph node needs it.**
Architecture v1.0 keeps Redis for "caching, ephemeral agent state, task queueing" — and LangGraph's checkpointing (needed for resumability, explicitly called out as a value of choosing LangGraph in the frozen doc) requires a checkpointer backend to be wired in **at graph-compile time**, not bolted on later. If Redis is introduced in, say, Milestone 6, then Milestones 3–5's graphs would either compile without checkpointing (silently losing the resumability property the architecture doc justified LangGraph with) or need to be re-touched once Redis lands. **Resolution: Redis connection layer is Milestone 1**, before anything graph-shaped is built, mirroring exactly how Phase 1 built the Postgres connection layer before anything that used it.

**2. Typed agent I/O contracts must exist before the first agent, not "whenever the second agent makes duplication obvious."**
The frozen architecture is explicit: *"every agent's input/output is a typed contract, checked at graph-build time, so a bad agent change fails fast."* If the first domain agent (Milestone 3) is built with an ad hoc return shape and the schema layer is added in Milestone 5 once there are enough agents to notice the pain, that's exactly the "discover missing architecture halfway through" failure mode this task is explicitly trying to prevent. **Resolution: `orchestrator/schemas/` — the `AgentInput`/`AgentOutput`/`Evidence`/`ComplexityTier`/graph state contracts — are defined as part of Milestone 2, before the first real agent is written in Milestone 3.**

**3. The episodic-log table (`investigations`) is a dependency of the *first* graph run, not of Synthesis.**
It's tempting to file "durable investigation logging" under Synthesis/Critic (Milestone 8) since that's where a full answer first exists. But Architecture v1.0's memory model (§3.4) treats the episodic Postgres log as recording *the full task graph progress*, not just final answers — and the SSE streaming/polling API (§3.5) needs an `investigation_id` to exist from the moment a query is accepted, before any agent has produced anything. If this table is designed in Milestone 8, Milestones 3–7 have nowhere to durably record progress, and the streaming API (Milestone 10) has no identifier to stream against retroactively. **Resolution: the `investigations` table and its migration are part of Milestone 2, alongside the schema contracts, before any agent exists.**

**4. MCP servers wrap tools that domain agents already need in Milestones 3 and 5 — they can't be deferred to the last milestone without creating two competing tool-call code paths.**
Architecture v1.0 scoped MCP narrowly to Seismic + Literature (§1.2 of the prior review). If Seismic's agent (Milestone 3, as the first domain agent per the "simplest agent first" sequencing logic) is built calling USGS directly and *then* Milestone 10 wraps it in MCP, the agent's tool-calling code gets rewritten, not extended. **Resolution: the MCP server for whichever domain is built first is stood up in that same milestone, not deferred.** Given Milestone 3 builds the Air Quality agent first (simplest, single-source, per the original Phase 1 roadmap's own precedent of picking the simplest agent to prove the skeleton), and Air Quality was **not** one of the two domains scoped for MCP, this dependency doesn't actually collide — Air Quality stays a plain typed tool call, and Seismic (built in Milestone 5) gets its MCP wrapper *in Milestone 5*, not deferred to Milestone 10. Literature's MCP wrapper is built alongside the Literature/RAG agent itself in Milestone 6, not deferred either. **Milestone 10 is re-scoped to SSE streaming only — MCP wrapping is pulled forward into the milestones that build those specific agents.**

These four corrections are reflected in the milestone list below; I is not going to re-explain them per-milestone, just flag with "**(pre-flight fix applied)**" where relevant.

---

## 1. Phase 2 Repository Structure

```
gaiaos/
├── cache/                          # NEW — Redis connection layer (mirrors db/ from Phase 1)
│   ├── __init__.py
│   ├── client.py                   # async Redis client, connection lifecycle
│   └── keys.py                     # centralized key-naming functions (no magic strings elsewhere)
│
├── orchestrator/
│   ├── graph/
│   │   ├── state.py                # NEW — TaskGraphState (LangGraph state schema)
│   │   ├── builder.py              # NEW — graph construction, conditional edges
│   │   └── checkpointer.py         # NEW — Redis-backed LangGraph checkpointer wiring
│   ├── agents/
│   │   ├── supervisor/
│   │   │   ├── planner.py          # decomposition + complexity classification
│   │   │   └── prompts.py
│   │   ├── air_quality/            # first domain agent (M3)
│   │   ├── seismic/                # M5, ships with its MCP server
│   │   ├── ocean/                  # M5
│   │   ├── atmosphere/             # M5
│   │   ├── wildfire/               # M5
│   │   ├── literature_rag/         # M6, ships with its MCP server
│   │   ├── causal_chain/           # M7
│   │   ├── synthesis/              # M8
│   │   ├── critic/                 # M8
│   │   └── simulation/             # M9
│   └── schemas/
│       ├── agent_io.py             # NEW (M2) — AgentInput, AgentOutput, Evidence
│       ├── complexity.py           # NEW (M2) — ComplexityTier enum
│       └── graph_state.py          # NEW (M2) — shared TypedDict/Pydantic graph state
│
├── mcp_servers/
│   ├── seismic_usgs/                # NEW — M5
│   └── literature_search/           # NEW — M6
│
├── tools/                           # plain typed tool wrappers (non-MCP)
│   ├── air_quality_openaq/          # NEW — M3
│   ├── ocean_noaa/                  # NEW — M5
│   ├── weather/                     # NEW — M5
│   └── wildfire_firms/              # NEW — M5
│
├── simulation_engine/                # NEW — M9, statistical models only per frozen scope
│
├── db/
│   └── models/                       # NEW — first real ORM models (Phase 1 left Base.metadata empty)
│       ├── investigation.py          # M2
│       ├── hazard_event.py           # M7
│       └── literature_chunk.py       # M6
│
├── data/migrations/versions/
│   ├── 0002_investigations.py        # M2
│   ├── 0003_literature_chunks.py     # M6
│   ├── 0004_hazard_events.py         # M7
│   └── 0005_eval_benchmarks.py       # M1
│
├── eval/
│   ├── benchmarks/                   # M1 — curated question set (data, not code)
│   ├── harness/                      # M1 — runner + scoring
│   └── metrics/                      # M1 — calibration, retrieval precision, etc.
│
├── app/api/v1/
│   └── investigations.py             # NEW — M2 (create/get), M10 (stream)
│
└── docs/
    └── phase2/                       # NEW — this document's living counterpart, updated per milestone
```

**Dependency direction (extends Phase 1's documented contract):**
- `cache → config` only (mirrors `db → config`). Never `cache → orchestrator`.
- `orchestrator/schemas → ` nothing project-internal (pure types), so every other orchestrator module can depend on it with zero cycle risk — same pattern Phase 1 used for `db/base.py`.
- `orchestrator/agents/* → orchestrator/schemas`, `tools/*` or `mcp_servers/*`, `cache`, `db` — never `→ app`.
- `mcp_servers/* → tools/*` internally where they wrap the same underlying API call (e.g., `mcp_servers/seismic_usgs` calls the same client code `tools/` would, just exposes it over the MCP protocol) — avoids the duplication risk flagged in the Phase 1 audit (§13, finding #6) from recurring here.
- `app/api/v1/investigations.py → orchestrator/graph` (invokes the compiled graph), never the reverse.

---

## 2. API Design (designed up front, per instructions)

### `POST /api/v1/investigations`
Creates an investigation and kicks off graph execution asynchronously.

**Request model** (`InvestigationCreateRequest`):
```python
class InvestigationCreateRequest(BaseModel):
    query: str = Field(min_length=3, max_length=2000)
```

**Response model** (`InvestigationCreateResponse`), `202 Accepted`:
```python
class InvestigationCreateResponse(BaseModel):
    investigation_id: UUID
    status: Literal["accepted"]
    stream_url: str      # /api/v1/investigations/{id}/stream
    poll_url: str         # /api/v1/investigations/{id}
```

**Errors:** `422` (validation, standard FastAPI), `503` (`ErrorResponse`) if the graph checkpointer's Redis backend is unreachable at accept-time — fail fast rather than accept a query that can never checkpoint.

### `GET /api/v1/investigations/{investigation_id}`
Polling fallback, per Architecture v1.0 §3.5's own explicit design ("investigation IDs + resumable status polling as a fallback to streaming").

**Response model** (`InvestigationStatusResponse`):
```python
class InvestigationStatusResponse(BaseModel):
    investigation_id: UUID
    status: Literal["planning", "gathering", "synthesizing", "verifying", "complete", "failed"]
    complexity_tier: ComplexityTier | None
    answer: str | None
    confidence: float | None = Field(None, ge=0.0, le=1.0)
    evidence_gaps: list[str] = []
    execution_trace: dict | None      # populated once complete; the explainability artifact
    created_at: datetime
    completed_at: datetime | None
```

**Errors:** `404` (`ErrorResponse`) if `investigation_id` doesn't exist.

### `GET /api/v1/investigations/{investigation_id}/stream` (Milestone 10)
SSE endpoint. Emits one event per graph-node transition:

```
event: planning
data: {"status": "planning"}

event: agent_started
data: {"agent": "seismic", "at": "2026-08-01T12:00:03Z"}

event: agent_completed
data: {"agent": "seismic", "evidence_count": 3}

event: synthesizing
data: {}

event: critic_flag
data: {"claim": "...", "confidence": 0.4, "reason": "single-source"}

event: done
data: {"investigation_id": "...", "status": "complete"}
```

Client timeout mitigation (per Architecture v1.0 §3.5's own design review) means the stream endpoint and the poll endpoint share the same underlying `investigations` row — a client can drop the SSE connection at any point and resume via polling with no data loss.

**Common error model** (all endpoints):
```python
class ErrorResponse(BaseModel):
    detail: str
    error_code: str   # e.g. "investigation_not_found", "checkpointer_unavailable"
```
This mirrors Phase 1's `ReadinessFailureResponse` pattern (specific `reason`, no stack traces, no leakage) rather than inventing a new error shape.

---

## 3. Database Design (designed up front, per instructions)

### `investigations` (Milestone 2)
```sql
CREATE TABLE investigations (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_text         TEXT NOT NULL,
    complexity_tier    TEXT,                     -- 'trivial' | 'moderate' | 'complex'
    status             TEXT NOT NULL DEFAULT 'planning',
    answer             TEXT,
    confidence         NUMERIC(3,2),
    execution_trace    JSONB,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at       TIMESTAMPTZ
);
CREATE INDEX ix_investigations_status ON investigations (status);
CREATE INDEX ix_investigations_created_at ON investigations (created_at DESC);
```
**Reasoning:** `execution_trace JSONB` is the explainability artifact from Architecture v1.0 §3.9 — stored, not recomputed, so the eval harness (M1) can sample historical traces without re-running graphs. Indexed on `status` (poll/stream endpoints filter on it) and `created_at DESC` (recency-biased eval sampling, admin listing later). No foreign key to a `users` table yet — auth is still Phase 1's `AuthStub`; a nullable `user_id` column is deliberately **not** added here to avoid a half-used column — it's added in the milestone that actually wires real auth (outside Phase 2 scope, see §7).

### `hazard_events` + `hazard_relationships` (Milestone 7)
```sql
CREATE TABLE hazard_events (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type         TEXT NOT NULL,             -- 'earthquake' | 'flood' | 'wildfire' | ...
    region             GEOMETRY(Point, 4326),      -- PostGIS, matches frozen architecture's PostGIS scope
    occurred_at        TIMESTAMPTZ NOT NULL,
    severity           NUMERIC,
    source             TEXT NOT NULL,
    raw_data           JSONB NOT NULL,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_hazard_events_type_time ON hazard_events (event_type, occurred_at DESC);
CREATE INDEX ix_hazard_events_region ON hazard_events USING GIST (region);

CREATE TABLE hazard_relationships (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_event_id       UUID NOT NULL REFERENCES hazard_events(id) ON DELETE CASCADE,
    to_event_id         UUID NOT NULL REFERENCES hazard_events(id) ON DELETE CASCADE,
    relationship_type   TEXT NOT NULL,             -- 'preceded' | 'correlated_with' | ...
    confidence          NUMERIC(3,2),
    notes               TEXT,
    UNIQUE (from_event_id, to_event_id, relationship_type)
);
CREATE INDEX ix_hazard_rel_from ON hazard_relationships (from_event_id);
```
**Reasoning:** this is the v2-deferred-Neo4j decision made concrete — a self-referential relationship table plus recursive CTE traversal (query pattern documented in Milestone 7 below), exactly per the frozen architecture's ruling. `ON DELETE CASCADE` on both FKs so a deleted event doesn't leave orphaned relationship rows. `GIST` index on `region` because every geospatial query this table will ever receive (radius search, "near this coastline") needs it — omitting it here would be the one index Phase 1's DB audit would have flagged immediately.

### `literature_chunks` (Milestone 6)
```sql
CREATE TABLE literature_chunks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     TEXT NOT NULL,
    chunk_text      TEXT NOT NULL,
    embedding       VECTOR(1536),
    source_url      TEXT,
    metadata        JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_literature_chunks_document ON literature_chunks (document_id);
CREATE INDEX ix_literature_chunks_embedding ON literature_chunks
    USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ix_literature_chunks_fts ON literature_chunks
    USING GIN (to_tsvector('english', chunk_text));
```
**Reasoning:** `HNSW` (not `IVFFlat`) chosen because pgvector's HNSW index doesn't require a pre-populated table to build effectively (IVFFlat needs representative data present before `CREATE INDEX` for good cluster quality) — better fit for a corpus that grows incrementally. The `GIN`/`tsvector` index exists specifically because Architecture v1.0 §3.3 mandates **hybrid** rank fusion (vector + BM25/full-text), not vector-only — omitting this index would silently make the "hybrid" retrieval strategy a vector-only one in practice, contradicting the frozen design.

### `eval_benchmark_questions` + `eval_benchmark_runs` (Milestone 1)
```sql
CREATE TABLE eval_benchmark_questions (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question_text           TEXT NOT NULL,
    expected_domains        TEXT[] NOT NULL,
    expected_complexity     TEXT NOT NULL,
    reference_answer        TEXT NOT NULL,
    reference_evidence      JSONB,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE eval_benchmark_runs (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    benchmark_question_id    UUID NOT NULL REFERENCES eval_benchmark_questions(id) ON DELETE CASCADE,
    investigation_id         UUID REFERENCES investigations(id) ON DELETE SET NULL,
    orchestrator_version     TEXT NOT NULL,
    score                    NUMERIC(3,2),
    metrics                  JSONB,
    run_at                   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_eval_runs_version ON eval_benchmark_runs (orchestrator_version, run_at DESC);
```
**Reasoning:** `investigation_id` is nullable + `ON DELETE SET NULL` (not `CASCADE`) — a benchmark run's *score* is meaningful evaluation history worth keeping even if the underlying investigation row is later pruned/archived; only the raw investigation is disposable, the eval record isn't. `orchestrator_version` (a git-SHA-or-semver string set at deploy time, plumbed through `config/settings.py`) is what makes the "re-run before every deploy, catch silent regressions" requirement from the frozen architecture's eval section actually queryable — without this column, regression detection has no way to compare "today's run" against "last week's run" of the same benchmark set.

---

## 4. Milestones

Each milestone below is scoped to be independently mergeable, matching Phase 1's own discipline (one branch, one milestone, don't start N+1 before N merges — Phase 1 finding §13/#5 was a violation of this; Phase 2 restates it explicitly per milestone).

---

### Milestone 1 — Redis Connection Layer + Evaluation Harness Foundation

**1. Goal:** Stand up the Redis connection layer (mirroring Phase 1's `db/session.py` pattern) and the evaluation harness's data layer and scoring runner — no agents exist yet, so the harness is built and validated against hand-written fixture data.

**2. Why it exists:** Both are hard prerequisites for every subsequent milestone (§0, points 1 and — indirectly — the eval-first discipline the frozen architecture explicitly regretted not doing in Phase 1).

**3. Dependencies:** Phase 1 `config/settings.py` (add `REDIS_URL`), Phase 1 `db/session.py` pattern to mirror.

**4. Repository structure:** `cache/` (new package), `eval/harness/`, `eval/metrics/`, `data/migrations/versions/0005_eval_benchmarks.py`.

**5. Files to create:** `cache/__init__.py`, `cache/client.py`, `cache/keys.py`, `eval/harness/runner.py`, `eval/harness/scorer.py`, `eval/metrics/calibration.py`, `eval/metrics/retrieval_precision.py`, `db/models/eval_benchmark.py`, migration `0005_eval_benchmarks.py`, `tests/test_cache.py`, `tests/test_eval_harness.py`.

**6. Files to modify:** `config/settings.py` (add `REDIS_URL: str`, validated non-empty outside dev, same pattern as `DATABASE_URL`), `docker-compose.yml` (add `redis` service + healthcheck), `app/main.py` (init/dispose Redis client in lifespan, same pattern as the DB engine).

**7. Public interfaces:**
```python
# cache/client.py
async def get_redis() -> Redis: ...          # DI-injectable, mirrors get_db_session
async def init_redis(settings: Settings) -> None: ...
async def dispose_redis() -> None: ...

# eval/harness/runner.py
async def run_benchmark_suite(orchestrator_version: str) -> BenchmarkSuiteResult: ...
```

**8. Internal classes:** `BenchmarkSuiteResult` (Pydantic), `RedisKeyBuilder` (in `cache/keys.py` — centralizes `f"gaiaos:cache:{...}"` / `f"gaiaos:checkpoint:{...}"` string construction so no other module hand-builds Redis keys, preventing key-collision bugs later).

**9. Data flow:** `run_benchmark_suite` reads `eval_benchmark_questions` → (in M1, since no graph exists yet) scores against a null/fixture runner that always returns "not yet implemented" with score `null` → writes `eval_benchmark_runs` rows anyway, so the historical time series exists from day one, even before there's anything real to score. This deliberately establishes the eval-run table's shape and CI wiring *before* it has real signal to record — matching the frozen architecture's own regret ("build the eval harness first, before adding more agents").

**10. Sequence (text):**
```
CI/cron trigger → runner.run_benchmark_suite(version)
  → SELECT * FROM eval_benchmark_questions
  → for each question: [M1: stub result] / [M2+: invoke graph, await completion]
  → scorer.score(question, result) → BenchmarkSuiteResult
  → INSERT eval_benchmark_runs (bulk)
```

**11. Error handling:** Redis connection failure at startup → same fail-fast pattern as Phase 1's DB checks (raise at lifespan startup, don't let the app boot half-configured). Individual benchmark question failures don't abort the suite — caught, recorded as `score=null, metrics={"error": ...}`, suite continues (one broken fixture shouldn't blind the whole regression signal).

**12. Logging requirements:** structured log per benchmark run (`question_id`, `score`, `duration_ms`) via the existing Phase 1 `structlog` pipeline — no new logging infrastructure needed, just new call sites.

**13. Testing strategy:** Unit — `RedisKeyBuilder` key-format tests, `Settings` validation extended for `REDIS_URL`. Integration — real Redis container in CI (same pattern as real Postgres in Phase 1, not mocked), `init_redis`/`dispose_redis` lifecycle test. Failure-path — Redis unreachable → app fails to start with a clear error (test asserts this, mirroring the Phase 1 audit's own recommendation to test failure branches, not just success). Edge case — empty `eval_benchmark_questions` table → `run_benchmark_suite` returns an empty-but-valid result, not an error.

**14. CI impact:** add `redis` service to `docker-compose.yml`/CI compose stack; add `alembic upgrade head` **actually invoked in CI** (this is where Phase 1's Critical finding #1 gets closed out, since Milestone 2's migration is the first one to matter functionally — noting it here since M1's own migration, `0005`, is the first to actually be exercised by the now-fixed CI pipeline).

**15. Documentation impact:** `README.md` gets a Redis section mirroring the existing Postgres one; `docs/phase2/eval_harness.md` documents how to add a new benchmark question.

**16. Definition of Done:** `docker compose up` brings up Redis alongside Postgres; `run_benchmark_suite` executes against a hand-seeded fixture question and writes a real row; all tests green in CI including the new Redis failure-path test.

**17. Risks:** None significant — this is infrastructure-only, same risk profile as Phase 1's DB milestone.

**18. Future extensibility:** `RedisKeyBuilder` namespacing (`gaiaos:cache:*`, `gaiaos:checkpoint:*`, `gaiaos:ratelimit:*`) is designed now so Milestone 7 (real rate limiting, if ever un-stubbed) reuses the same key builder instead of inventing a second convention.

---

### Milestone 2 — Orchestrator Schemas, Episodic Log, Graph Skeleton, Trivial-Path Supervisor + Air Quality Agent

**1. Goal:** Build the typed agent-contract layer, the `investigations` table, a minimal compiled LangGraph with exactly one real path (trivial → single agent → response), and the first domain agent (Air Quality, chosen as the simplest single-source domain).

**2. Why it exists:** This is the "prove the skeleton end-to-end on the cheapest possible path" milestone — every later milestone adds nodes to a graph that already works, rather than debugging graph mechanics and agent logic simultaneously for the first time on a complex multi-agent path.

**3. Dependencies:** M1 (Redis, for the checkpointer).

**4. Repository structure:** `orchestrator/schemas/{agent_io,complexity,graph_state}.py`, `orchestrator/graph/{state,builder,checkpointer}.py`, `orchestrator/agents/supervisor/`, `orchestrator/agents/air_quality/`, `tools/air_quality_openaq/`, `db/models/investigation.py`, `app/api/v1/investigations.py`.

**5. Files to create:** all of the above, plus `data/migrations/versions/0002_investigations.py`, `tests/test_schemas.py`, `tests/test_graph_builder.py`, `tests/test_air_quality_agent.py`, `tests/test_investigations_api.py`.

**6. Files to modify:** `app/api/v1/router.py` (mount `investigations` router), `config/settings.py` (add `OPENAQ_API_KEY` if required by the provider, `ORCHESTRATOR_VERSION`).

**7. Public interfaces:**
```python
# orchestrator/schemas/agent_io.py
class Evidence(BaseModel):
    source: str
    claim: str
    confidence: float = Field(ge=0.0, le=1.0)
    retrieved_at: datetime

class AgentInput(BaseModel):
    investigation_id: UUID
    query: str
    region_hint: str | None = None

class AgentOutput(BaseModel):
    agent_name: str
    evidence: list[Evidence]
    errors: list[str] = []

# orchestrator/schemas/complexity.py
class ComplexityTier(str, Enum):
    TRIVIAL = "trivial"
    MODERATE = "moderate"
    COMPLEX = "complex"

# orchestrator/graph/builder.py
def build_graph(checkpointer: BaseCheckpointSaver) -> CompiledGraph: ...

# orchestrator/agents/air_quality/agent.py
async def run(input: AgentInput) -> AgentOutput: ...
```

**8. Internal classes:** `TaskGraphState` (TypedDict, per LangGraph convention — `investigation_id`, `query`, `complexity_tier`, `agent_outputs: list[AgentOutput]`, `final_answer: str | None`); `InvestigationRepository` (thin wrapper around the `investigations` table — `create`, `update_status`, `get` — so route handlers and graph nodes never hand-write SQL, following Phase 1's precedent of centralizing DB access patterns like `verify_extensions()`).

**9. Data flow:**
```
POST /investigations → InvestigationRepository.create(query) → row status='planning'
  → graph.ainvoke(TaskGraphState{...}, config={"thread_id": investigation_id})
  → Supervisor node: classify → TRIVIAL (only path that exists in M2)
  → Air Quality agent node: tools/air_quality_openaq → AgentOutput
  → terminal node: InvestigationRepository.update_status('complete', answer=...)
```

**10. Sequence diagram (text):**
```
Client -> API: POST /investigations {query}
API -> InvestigationRepository: create()
API -> Graph: ainvoke(state, thread_id=investigation_id)   [fire-and-forget task]
API -> Client: 202 {investigation_id, poll_url, stream_url}
Graph -> Supervisor: classify(query)
Supervisor -> Graph: complexity_tier=TRIVIAL
Graph -> AirQualityAgent: run(AgentInput)
AirQualityAgent -> OpenAQ API: fetch current readings
OpenAQ API -> AirQualityAgent: readings
AirQualityAgent -> Graph: AgentOutput(evidence=[...])
Graph -> Repository: update_status('complete', answer, execution_trace)
Client -> API: GET /investigations/{id}   [polls until status=complete]
```

**11. Error handling:** `AgentOutput.errors` carries tool-call failures without raising (an agent that can't reach OpenAQ returns evidence=[], errors=["OpenAQ unreachable"], not an exception) — this establishes the pattern every later agent (M3–M9) must follow, per the frozen architecture's "Synthesis must proceed with explicit gaps, never fabricate" rule (§3.10 of the original architecture doc), which starts being enforced structurally *here*, at the single-agent stage, not retrofitted later. Graph-level failures (checkpointer unreachable, unhandled exception in a node) mark the investigation `status='failed'` with a safe error message — never leave a row stuck in `planning` forever.

**12. Logging requirements:** every graph node transition logged with `investigation_id`, `node_name`, `duration_ms` — this is the seed of the execution-trace explainability feature (full node-by-node detail is assembled from these log events plus the final state, both written to `execution_trace JSONB`).

**13. Testing strategy:** Unit — `Evidence`/`AgentOutput` schema validation (bounds on `confidence`), `TaskGraphState` shape. Integration — full `POST → poll until complete → assert answer non-null` against a **mocked** OpenAQ HTTP layer (not a live external call in CI, to avoid flaking on third-party rate limits — first instance of this pattern, restated for every later agent milestone). Failure-path — OpenAQ mock returns 500 → assert `AgentOutput.errors` populated and investigation still reaches `status='complete'` with an evidence gap noted, not `status='failed'`. Edge case — empty query string (422 before it ever reaches the graph).

**14. CI impact:** CI now needs an HTTP-mocking layer (`respx` or `pytest-httpx`) added to `requirements/dev.txt` — first new CI dependency category since Phase 1.

**15. Documentation impact:** `docs/phase2/agent_contract.md` — documents the `AgentInput`/`AgentOutput` contract every future domain agent (M5 onward) must implement, so M5's four agents are built against a written spec, not tribal knowledge from reading M2's code.

**16. Definition of Done:** a trivial air-quality query submitted via `POST /investigations` reaches `status='complete'` with real evidence, polling and the full round trip covered by integration tests, migration `0002` applied via the now-CI-enforced `alembic upgrade head`.

**17. Risks:** LangGraph's checkpointer API surface is the least Phase-1-precedented part of this milestone (nothing in Phase 1 touched it) — budget extra time here specifically for checkpointer wiring, not the agent logic, which is straightforward.

**18. Future extensibility:** every subsequent domain agent (M5) and the Literature/Causal/Simulation agents (M6/M7/M9) implement the exact same `AgentInput → AgentOutput` interface defined here — no agent gets a bespoke contract.

---

### Milestone 3 — Adaptive Planner: Complexity Classifier + Conditional Routing

**1. Goal:** Replace the hardcoded `TRIVIAL`-only path from M2 with a real classifier and a genuine conditional edge that can route to either the trivial single-agent path or a (currently still-empty, until M5) multi-agent fan-out path.

**2. Why it exists:** This is the architecture's own named differentiator (Adaptive Planner) and the direct fix for the cost/latency concern raised in the original architecture review — it needs to exist before a second domain agent is added (M5), so M5 never has a period where "every query fans out to every agent" is the only behavior that exists.

**3. Dependencies:** M2 (graph skeleton, Supervisor node stub).

**4. Repository structure:** extends `orchestrator/agents/supervisor/` only.

**5. Files to create:** `orchestrator/agents/supervisor/classifier.py`, `tests/test_classifier.py`.

**6. Files to modify:** `orchestrator/agents/supervisor/planner.py` (real classification logic replacing the M2 stub), `orchestrator/graph/builder.py` (add the conditional edge).

**7. Public interfaces:**
```python
async def classify(query: str) -> ComplexityTier: ...
```

**8. Internal classes:** none new — this milestone is intentionally small in surface area, since it's inserting logic into an existing seam (`builder.py`'s conditional edge), not building new plumbing.

**9. Data flow:** `query → classify() [fast/cheap model call] → ComplexityTier → conditional edge selects next node(s)`.

**10. Sequence (text):**
```
Graph -> Supervisor: classify(query)
Supervisor -> Fast Model: "classify this query's domain scope and complexity"
Fast Model -> Supervisor: {tier, domains}
Supervisor -> Graph: state.complexity_tier = tier
Graph -> [conditional edge]:
   if TRIVIAL -> single matched domain agent
   if MODERATE/COMPLEX -> fan-out node (built in M5; in M3 this branch exists but has only Air Quality as a possible target until M5 lands)
```

**11. Error handling:** classifier call failure → default to `MODERATE` (fail toward *more* investigation, never silently drop to trivial and under-serve a complex query — a deliberate fail-safe direction, documented as such).

**12. Logging requirements:** log the classification decision and its rationale (`tier`, `matched_domains`, `raw_model_output`) — this is itself part of the explainability trace (users can eventually see *why* a query got routed a particular way).

**13. Testing strategy:** Unit — classifier against a fixed set of example queries with known expected tiers (regression-style test, not fuzzy). Integration — conditional edge routes correctly for both tiers end-to-end. Failure-path — classifier exception → asserts fallback to `MODERATE`. Edge case — ambiguous query (mixed trivial/complex signals) — documented expected behavior, tested explicitly rather than left undefined.

**14. CI impact:** none beyond existing test suite growth.

**15. Documentation impact:** `docs/phase2/adaptive_planner.md` — the classification taxonomy (what makes a query trivial vs. moderate vs. complex), since this is exactly the kind of judgment call a future contributor will want to extend and needs written criteria for, not just code to reverse-engineer.

**16. Definition of Done:** the same air-quality trivial query from M2 still completes correctly; a synthetic "moderate" query correctly routes to the fan-out branch (even though M5 hasn't populated it with real agents yet — the routing itself is what's being proven).

**17. Risks:** classifier miscalibration (over-routing everything to COMPLEX, defeating the cost-optimization purpose) — mitigated by the benchmark suite (M1) being extended with complexity-labeled fixtures so this is measurable, not just asserted.

**18. Future extensibility:** M5's fan-out node reads `state.complexity_tier`'s matched domains directly — no rework needed when real multi-agent fan-out lands.

---

### Milestone 4 — Remaining Domain Agents (Seismic, Ocean, Atmosphere, Wildfire) + Seismic MCP Server + Async Fan-Out

**1. Goal:** Implement the four remaining domain agents against the M2 contract, wire real async fan-out for the `MODERATE`/`COMPLEX` path, and stand up the Seismic MCP server alongside the Seismic agent **(pre-flight fix applied — MCP pulled forward from M10)**.

**2. Why it exists:** This is where the "genuinely parallel evidence-gathering" claim from the frozen architecture becomes real and testable, not theoretical.

**3. Dependencies:** M2 (contract, graph skeleton), M3 (routing must exist to actually reach a multi-agent path).

**4. Repository structure:** `orchestrator/agents/{seismic,ocean,atmosphere,wildfire}/`, `mcp_servers/seismic_usgs/`, `tools/{ocean_noaa,weather,wildfire_firms}/`.

**5. Files to create:** four agent modules, `mcp_servers/seismic_usgs/server.py`, three tool wrapper modules, `tests/test_{seismic,ocean,atmosphere,wildfire}_agent.py`, `tests/test_fan_out.py`, `tests/test_seismic_mcp_server.py`.

**6. Files to modify:** `orchestrator/graph/builder.py` (fan-out/fan-in nodes, `asyncio.gather`-based parallel dispatch), `config/settings.py` (four new API-key/endpoint settings).

**7. Public interfaces:** each agent implements the same `run(AgentInput) -> AgentOutput` from M2 — no new public surface at the contract level, by design. `mcp_servers/seismic_usgs/server.py` exposes `get_recent_earthquakes(region: str, min_magnitude: float, since: datetime) -> list[dict]` as an MCP tool.

**8. Internal classes:** `FanOutCoordinator` (wraps `asyncio.gather` over the matched-domain agent list from `state`, with **per-tool timeout + partial-results policy** — directly implementing the frozen architecture's own documented mitigation for "a slow/rate-limited external API stalls one branch of the fan-out").

**9. Data flow:**
```
Graph (MODERATE/COMPLEX) → FanOutCoordinator.run(matched_domains, investigation_id)
  → asyncio.gather(*[agent.run(input) for agent in matched_domains], return_exceptions=True)
  → per-agent timeout (configurable, default from architecture doc's own "~10–30s per domain agent" budget)
  → AgentOutput[] (partial results included, timed-out agents contribute an errors entry, not a hard failure)
```

**10. Sequence (text):**
```
Graph -> FanOutCoordinator: run([seismic, ocean], investigation_id)
par
  FanOutCoordinator -> SeismicAgent: run(input)
  SeismicAgent -> MCP Server (seismic_usgs): get_recent_earthquakes(...)
  MCP Server -> USGS API: fetch
  USGS API -> MCP Server: data
  MCP Server -> SeismicAgent: AgentOutput
and
  FanOutCoordinator -> OceanAgent: run(input)
  OceanAgent -> NOAA tool wrapper: fetch
  NOAA tool wrapper -> OceanAgent: AgentOutput
end
FanOutCoordinator -> Graph: [AgentOutput, AgentOutput]  (or partial, on timeout)
```

**11. Error handling:** `return_exceptions=True` on `gather` — one agent's exception never aborts siblings. Explicit per-tool timeout raises a caught `TimeoutError`, converted to `AgentOutput(evidence=[], errors=["timed out after Ns"])`, exactly matching the M2-established pattern. Synthesis (M8) is what actually surfaces these gaps to the end user — this milestone's job is only to make sure a partial failure never becomes a hard failure.

**12. Logging requirements:** per-agent start/complete/timeout events logged with `investigation_id`, `agent_name`, `duration_ms`, `outcome` — feeds the SSE `agent_started`/`agent_completed` events designed in §2 (M10 consumes these same log events, not a separate mechanism).

**13. Testing strategy:** Unit — each agent tested individually against mocked external APIs (same `respx`/`pytest-httpx` pattern from M2). Integration — `FanOutCoordinator` with 2+ agents, asserting true concurrency (wall-clock time ≈ max(agent times), not sum — a real, checkable assertion, not just "looks async"). Failure-path — one agent times out, one succeeds → assert graph still reaches `status='complete'` with a partial-evidence note. Edge case — all agents fail simultaneously → investigation still resolves to `complete` with an explicit "no evidence gathered" answer, never silently hangs.

**14. CI impact:** none beyond existing patterns extended to four more agents; CI runtime grows linearly, worth monitoring but not yet a problem at this scale.

**15. Documentation impact:** `docs/phase2/mcp_servers.md` — documents which two domains get MCP wrappers and explicitly why the other domains don't (pointing back to the original scoping rationale), so a future contributor doesn't "helpfully" MCP-wrap everything.

**16. Definition of Done:** a moderate-complexity synthetic query (e.g., "earthquake and ocean temperature near X") fans out to Seismic + Ocean concurrently, both return real (mocked-in-test, real-in-manual-verification) evidence, and the Seismic MCP server is independently invocable by an external MCP client (manually verified against Claude Desktop, per the original architecture's stated value of MCP giving a second consumer for free).

**17. Risks:** four agents in one milestone is the single largest-surface-area milestone in Phase 2 — if velocity is a concern, this is the one milestone that could reasonably be split into two PRs (Seismic+MCP as 4a, Ocean/Atmosphere/Wildfire as 4b) without violating the "one milestone, one merge" discipline, since the fan-out coordinator itself doesn't require all four to land atomically.

**18. Future extensibility:** `FanOutCoordinator`'s timeout/partial-results policy is reused as-is by M6 (Literature) and M7 (Causal Chain) joining the fan-out set — no rework.

---

### Milestone 5 — Literature/RAG Agent + pgvector + Hybrid Retrieval + Literature MCP Server

**1. Goal:** Implement the Literature agent with hybrid (vector + BM25) retrieval per Architecture v1.0 §3.3, backed by the `literature_chunks` table, and its MCP server **(pre-flight fix applied — pulled forward from M10)**.

**2. Why it exists:** This is the one explicitly-scoped "actual RAG slice" of the whole system — everything else is structured/tool retrieval, per the frozen architecture's own insistence that RAG stay a small piece.

**3. Dependencies:** M2 (contract), M4 pattern (agent structure, fan-out participation).

**4. Repository structure:** `orchestrator/agents/literature_rag/`, `mcp_servers/literature_search/`, `db/models/literature_chunk.py`, ingestion script for seeding the corpus.

**5. Files to create:** agent module, MCP server module, `data/migrations/versions/0003_literature_chunks.py`, `ingestion/literature_seed.py` (one-time/periodic corpus loader — papers/reports → chunked → embedded → inserted), `tests/test_literature_agent.py`, `tests/test_hybrid_retrieval.py`.

**6. Files to modify:** `config/settings.py` (embedding model endpoint/key, if external; chunk size config).

**7. Public interfaces:**
```python
async def hybrid_search(query: str, k: int = 10) -> list[Evidence]: ...
```

**8. Internal classes:** `RankFusion` (combines vector-similarity rank and BM25/`ts_rank` rank into a single ordering — documented formula, e.g. reciprocal rank fusion, not a black box).

**9. Data flow:**
```
Literature Agent.run(input)
  → embed(input.query) → vector search (HNSW index) top-N
  → to_tsquery(input.query) → full-text search top-N
  → RankFusion.combine(vector_results, fts_results) → top-K
  → map to Evidence[] (source=document_id, claim=chunk summary, confidence=fusion score)
```

**10. Sequence (text):**
```
FanOutCoordinator -> LiteratureAgent: run(input)
LiteratureAgent -> Embedding Model: embed(query)
Embedding Model -> LiteratureAgent: vector
LiteratureAgent -> Postgres (pgvector): ANN search
LiteratureAgent -> Postgres (tsvector): full-text search
LiteratureAgent -> RankFusion: combine(results)
LiteratureAgent -> Graph: AgentOutput(evidence=[...])
```
The MCP server (`literature_search`) exposes the same `hybrid_search` as an MCP tool, called identically whether the caller is this graph or an external MCP client.

**11. Error handling:** embedding-model failure → agent returns `errors=["embedding service unreachable"]`, does not fall back to full-text-only silently (a silent degradation from "hybrid" to "keyword-only" would misrepresent retrieval quality in Synthesis without anyone knowing — explicit failure is safer than silent degradation here).

**12. Logging requirements:** log `query`, `vector_result_count`, `fts_result_count`, `fusion_top_k` — enables the eval harness's retrieval-precision metric (M1's `eval/metrics/retrieval_precision.py`) to actually be computed against real runs, not just fixtures.

**13. Testing strategy:** Unit — `RankFusion` combination logic against known input rankings (deterministic, no external calls). Integration — real Postgres with a small seeded fixture corpus (5–10 chunks), assert hybrid search outperforms either method alone on a known query. Failure-path — embedding service down → asserts explicit error, not silent fallback. Edge case — query with no matching chunks → empty `Evidence[]`, not an error.

**14. CI impact:** corpus seeding fixture data added to test setup; no new CI infra needed (reuses the same Postgres container).

**15. Documentation impact:** `docs/phase2/retrieval_strategy.md` — documents the rank-fusion formula and index choice (HNSW vs IVFFlat reasoning from §3), so a future tuning pass has a documented baseline to compare against, not a black box to reverse-engineer.

**16. Definition of Done:** a literature-heavy query returns evidence with citations traceable to `document_id`/`source_url`; MCP server independently callable; retrieval-precision metric computable from a real run and recorded via M1's harness.

**17. Risks:** corpus size at launch will be small (tens–hundreds of chunks per the original architecture's own scale assumption) — HNSW index quality at very small N is fine, but rank-fusion tuning is inherently noisy until the corpus grows; document this as an expected, not alarming, early-stage characteristic.

**18. Future extensibility:** if corpus scale later exceeds pgvector's comfortable range, Architecture v1.0 already documents the Qdrant migration trigger (§Future Scalability) — this milestone's `hybrid_search` interface is the abstraction boundary that migration would sit behind, so nothing here needs to anticipate it further.

---

### Milestone 6 — Causal Chain Agent (Postgres Recursive CTE)

**1. Goal:** Implement historical-analogue/causal-chain reasoning over `hazard_events`/`hazard_relationships` using bounded-depth recursive CTEs, per the frozen architecture's Neo4j-deferred decision.

**2. Why it exists:** This is the "similar seismic + ocean temperature patterns preceded X" reasoning capability — genuinely graph-shaped data, deliberately implemented without a graph database per the v1.0 ruling.

**3. Dependencies:** M2 (contract), M4's Seismic agent (a realistic source of `hazard_events` rows — this agent needs *some* populated event data to traverse, so a small seed/ingestion step for historical events is part of this milestone too, not assumed to exist).

**4. Repository structure:** `orchestrator/agents/causal_chain/`, `ingestion/hazard_event_seed.py`.

**5. Files to create:** agent module, `data/migrations/versions/0004_hazard_events.py`, `ingestion/hazard_event_seed.py`, `tests/test_causal_chain_agent.py`, `tests/test_recursive_cte.py`.

**6. Files to modify:** none outside new files — this agent joins the existing fan-out mechanism unmodified.

**7. Public interfaces:**
```python
async def find_causal_chain(event_type: str, region: str, max_depth: int = 4) -> list[Evidence]: ...
```

**8. Internal classes:** none new beyond the agent itself — deliberately thin, since the actual "engineering" here is the SQL, not application code.

**9. Data flow:**
```
CausalChainAgent.run(input)
  → find_causal_chain(matched event_type, region, max_depth=4)
  → recursive CTE traverses hazard_relationships up to max_depth
  → map matched chains to Evidence[] (claim = human-readable chain summary, confidence = min(edge confidences) along the chain)
```

**10. Sequence (text):**
```
FanOutCoordinator -> CausalChainAgent: run(input)
CausalChainAgent -> Postgres: WITH RECURSIVE chain AS (...) SELECT ... (depth <= 4)
Postgres -> CausalChainAgent: rows
CausalChainAgent -> Graph: AgentOutput(evidence=[...])
```

**11. Error handling:** query timeout (defensive statement_timeout set specifically for this recursive query, since an unbounded/misconfigured recursive CTE is a known Postgres footgun) → caught, returns `errors=["causal chain query exceeded time budget"]`, never lets a runaway recursive query hang the whole investigation.

**12. Logging requirements:** log `max_depth` used, `chain_count` returned, `query_duration_ms` — this duration is worth watching specifically because recursive CTE performance is the one place this milestone's design explicitly trades simplicity for a ceiling (documented migration trigger to Neo4j already exists in the frozen architecture if this becomes a bottleneck).

**13. Testing strategy:** Unit — CTE depth-limiting logic (max_depth=4 is actually enforced, not just documented). Integration — seeded fixture chain of 5 linked events, assert traversal finds the expected chain and stops at depth 4 even though a 5th link exists (proves the bound is real). Failure-path — statement timeout simulated (short timeout + deliberately slow fixture) → asserts graceful `errors` entry. Edge case — event with no relationships → empty result, not an error; cyclic relationship data (A→B→A) → recursive CTE must not infinite-loop (Postgres's `WITH RECURSIVE` requires an explicit cycle guard — tested explicitly, since this is the single most likely correctness bug in this milestone).

**14. CI impact:** none new.

**15. Documentation impact:** `docs/phase2/causal_chain.md` — the recursive CTE query itself, annotated, plus the documented Neo4j migration trigger restated here so it's discoverable from the code that would need to change, not only from the master architecture doc.

**16. Definition of Done:** a seeded 3–4-hop historical chain is correctly traversed and surfaced as evidence; cycle-safety and depth-bound both covered by tests.

**17. Risks:** cyclic-data correctness is the one real risk in this milestone — budget explicit test time for it, not just happy-path chain traversal.

**18. Future extensibility:** none needed within Phase 2 — Neo4j migration (if ever triggered) is explicitly Phase 3+ scope per the frozen architecture, not something this milestone needs to anticipate beyond keeping `find_causal_chain`'s interface stable as the abstraction boundary.

---

### Milestone 7 — Synthesis + Critic (Single-Pass, No Replan Loop)

**1. Goal:** Merge all `AgentOutput`s into a claim-by-claim, citation-mapped answer (Synthesis), then run exactly one verification pass over it (Critic) — no recursive replanning, per the frozen architecture's explicit v1 ruling.

**2. Why it exists:** This is where "evidence-backed answer" and "explainability enforcement" actually happen — the payoff milestone for everything M2–M6 gathered.

**3. Dependencies:** M2 (contract), M3 (routing), M4–M6 (at least one real evidence source needs to exist to synthesize over — technically only M2's Air Quality agent is a hard dependency, but this milestone is only meaningfully testable once M4–M6 exist too).

**4. Repository structure:** `orchestrator/agents/synthesis/`, `orchestrator/agents/critic/`.

**5. Files to create:** both agent modules, `orchestrator/schemas/synthesis.py` (new typed output: `SynthesizedClaim`, `SynthesisOutput`, `CriticFlag`), `tests/test_synthesis_agent.py`, `tests/test_critic_agent.py`.

**6. Files to modify:** `orchestrator/graph/builder.py` (fan-in → Synthesis → Critic → terminal edges), `db/models/investigation.py` (no schema change needed — `execution_trace`/`answer`/`confidence` columns already anticipate this from M2).

**7. Public interfaces:**
```python
async def synthesize(evidence: list[AgentOutput]) -> SynthesisOutput: ...
async def verify(synthesis: SynthesisOutput) -> list[CriticFlag]: ...
```
```python
class SynthesizedClaim(BaseModel):
    text: str
    supporting_evidence: list[Evidence]
    confidence: float

class SynthesisOutput(BaseModel):
    claims: list[SynthesizedClaim]
    evidence_gaps: list[str]     # domains that returned errors/no evidence, surfaced not hidden

class CriticFlag(BaseModel):
    claim_text: str
    flagged_reason: str
    severity: Literal["low", "medium", "high"]
```

**8. Internal classes:** `CitationMapper` (ensures every `SynthesizedClaim.supporting_evidence` traces back to an actual `AgentOutput.evidence` entry — structurally prevents the LLM from fabricating a citation that doesn't exist in the gathered evidence, by validating post-hoc against the actual evidence set rather than trusting the model's claim).

**9. Data flow:**
```
Graph fan-in → Synthesis.synthesize(all AgentOutputs)
  → SynthesisOutput (claims + explicit evidence_gaps, never fabricated for missing domains)
  → Critic.verify(SynthesisOutput)
  → CriticFlag[] (annotates, never blocks/removes claims — single pass, no replan per frozen ruling)
  → InvestigationRepository.update_status('complete', answer=rendered_text, confidence=avg, execution_trace={...})
```

**10. Sequence (text):**
```
Graph -> Synthesis: synthesize([AgentOutput, AgentOutput, ...])
Synthesis -> CitationMapper: validate each claim's citations
Synthesis -> Graph: SynthesisOutput
Graph -> Critic: verify(SynthesisOutput)
Critic -> Graph: CriticFlag[]
Graph -> Repository: update_status(complete, answer, confidence, trace)
```

**11. Error handling:** `CitationMapper` validation failure (model cited something not in evidence) → that specific claim is dropped from the final answer and logged as a synthesis integrity error, not silently kept — this is a hard structural guarantee, not a prompt-level request. Critic failure (model call errors) → investigation still completes with `critic_flags=[]` and a logged warning, since an unavailable Critic shouldn't block delivering an otherwise-good answer (verification failing open here is a deliberate, documented trade — different from the fail-closed choice made for the Redis checkpointer in M1, and the difference is intentional: an unreachable cache/state backend blocks correctness, an unreachable verification pass degrades confidence but the underlying answer is still real).

**12. Logging requirements:** log claim count, evidence-gap count, flag count/severity distribution per investigation — this is the core signal for the eval harness's confidence-calibration metric (M1).

**13. Testing strategy:** Unit — `CitationMapper` against a deliberately fabricated citation (must be caught and dropped). Integration — full graph run from query to synthesized+verified answer against multiple mocked domain agents. Failure-path — Critic unavailable → asserts investigation still completes with empty flags, not `status='failed'`. Edge case — zero evidence gathered across all agents (total external failure) → Synthesis must produce an explicit "unable to gather evidence" answer, never a fabricated one (direct enforcement of the frozen architecture's §3.10 requirement).

**14. CI impact:** none new beyond existing patterns.

**15. Documentation impact:** `docs/phase2/synthesis_and_critic.md` — explicitly documents the "single pass, no replan" scope boundary and points to the frozen architecture's own note that a bounded replan loop is v1.1/Phase 3 scope, not something to add opportunistically here.

**16. Definition of Done:** an end-to-end multi-domain query (fan-out across M4/M5/M6 agents) produces a synthesized answer with verifiable citations, critic flags recorded, and a complete `execution_trace` — this is the milestone where the system first does what the whole project is named for.

**17. Risks:** citation fabrication is the single highest-consequence failure mode in this entire phase (a hallucinated citation directly undermines the "explainability" value proposition the whole architecture is built around) — `CitationMapper`'s test coverage should be treated as the least-negotiable test suite in Phase 2.

**18. Future extensibility:** `CriticFlag` and the single-pass structure are deliberately shaped so a future bounded-replan loop (Phase 3+) can wrap this exact `synthesize → verify` pair in a retry loop without changing either function's interface.

---

### Milestone 8 — Simulation Agent (Statistical Models, Planner-Gated)

**1. Goal:** Implement the Simulation agent using statistical/existing-model forecasting (explicitly not a physics engine, per frozen scope), invoked only when the Adaptive Planner (M3) flags a query as needing prediction.

**2. Why it exists:** This is the one agent that produces genuine forward-looking prediction rather than retrieval — the "digital twin core" of the system, per the frozen architecture, but deliberately the last domain-capability milestone since it's gated and lower-frequency by design.

**3. Dependencies:** M3 (planner must be able to flag "needs prediction"), M7 (Synthesis must know how to handle simulation-flavored evidence, specifically uncertainty bounds).

**4. Repository structure:** `simulation_engine/`, `orchestrator/agents/simulation/`.

**5. Files to create:** `simulation_engine/models/{plume_dispersion,flood_extent,wildfire_spread,enso_forecast}.py` (statistical implementations, not physics), `orchestrator/agents/simulation/agent.py`, `tests/test_simulation_agent.py`, `tests/test_simulation_models.py`.

**6. Files to modify:** `orchestrator/agents/supervisor/classifier.py` (extend classification to also flag `needs_simulation: bool`), `orchestrator/schemas/agent_io.py` (extend `Evidence` or add a `SimulationOutput` subtype carrying explicit `uncertainty_bounds` and `assumptions` fields — a schema-level guarantee, not a prompt instruction, that Synthesis always has these fields to surface).

**7. Public interfaces:**
```python
class SimulationResult(BaseModel):
    prediction: str
    uncertainty_bounds: tuple[float, float]
    assumptions: list[str]
    model_used: str

async def run_simulation(hazard_type: str, region: str, parameters: dict) -> SimulationResult: ...
```

**8. Internal classes:** one class per model type (`PlumeDispersionModel`, `FloodExtentModel`, `WildfireSpreadModel` — cellular-automaton-based but explicitly bounded/coarse per scope, `ENSOForecastModel`) — each implementing a shared `SimulationModel` protocol (`run(parameters) -> SimulationResult`), so adding a fifth model type later doesn't require touching the agent, only adding a new class.

**9. Data flow:**
```
SimulationAgent.run(input)
  → select model by hazard_type
  → model.run(parameters derived from prior AgentOutputs in state, e.g. wind data from Atmosphere agent)
  → sanity-bound check (physically plausible range validation, per frozen architecture §3.10)
  → SimulationResult or errors=["simulation inconclusive"]
```

**10. Sequence (text):**
```
Graph -> SimulationAgent: run(input, prior_evidence=[AtmosphereOutput, ...])
SimulationAgent -> ModelRegistry: select(hazard_type)
SimulationAgent -> WildfireSpreadModel: run(parameters)
WildfireSpreadModel -> SimulationAgent: raw_result
SimulationAgent -> SanityBoundChecker: validate(raw_result)
alt within bounds
  SimulationAgent -> Graph: AgentOutput(evidence=[SimulationResult as Evidence])
else out of bounds
  SimulationAgent -> Graph: AgentOutput(errors=["simulation inconclusive"])
end
```

**11. Error handling:** `SanityBoundChecker` failure → **never** passes an implausible number to Synthesis as if it were valid — this is the direct, literal implementation of the frozen architecture's "failures return 'simulation inconclusive,' not a fabricated number" requirement (§3.10 of the original doc), enforced structurally here exactly as it was for evidence gaps in M2/M7.

**12. Logging requirements:** log `model_used`, `parameters`, `sanity_check_result` — simulation is the single most "trust me" component of the whole system, so its logs need to be the most complete, not the least.

**13. Testing strategy:** Unit — each `SimulationModel` against known-input/known-output fixtures (deterministic, since these are statistical models with fixed parameters in tests, not live physical simulations). Integration — SimulationAgent invoked only when planner flags `needs_simulation=True`, never otherwise (explicit assertion that trivial/moderate non-prediction queries never touch this agent — direct enforcement of the cost-optimization goal). Failure-path — sanity-bound violation → asserts `errors=["simulation inconclusive"]`, never a numeric result. Edge case — missing prior evidence the model needs (e.g., wildfire spread with no wind data available) → explicit `errors` entry, not a default/guessed parameter silently substituted.

**14. CI impact:** none new.

**15. Documentation impact:** `docs/phase2/simulation_models.md` — for each model, states explicitly what it is (a statistical/coarse approximation) and is not (a physics engine), restating the frozen architecture's own scope boundary at the point future contributors are most likely to be tempted to "improve" it into something heavier.

**16. Definition of Done:** a complex, prediction-requiring synthetic query correctly triggers Simulation (and only that query type does), produces a bounded result with explicit assumptions, and Synthesis correctly surfaces the uncertainty bounds in the final answer (verified by an integration test asserting the bounds appear in `SynthesisOutput`, not just that the simulation ran).

**17. Risks:** the temptation to scope-creep a "coarse cellular automaton" into something more physically detailed is the highest scope-creep risk in all of Phase 2 — explicitly flagged here as a risk to manage in code review, not just a technical risk.

**18. Future extensibility:** `SimulationModel` protocol means a genuinely more sophisticated model (a real physics-based one, if ever justified) can be swapped in behind the same interface without touching the agent or Synthesis — the abstraction boundary is deliberately placed here for exactly that reason.

---

### Milestone 9 — SSE Streaming, Investigation Polling Hardening, Explainability Trace Rendering

**1. Goal:** Build the client-facing streaming/polling API designed in §2, wire it to the log-event stream established across M2–M8, and finalize `execution_trace` rendering.

**2. Why it exists:** Every prior milestone produced the *content* of the explainability story (structured logs, evidence, citations, flags) — this milestone is where it becomes something a client can actually consume live, closing the loop on the frozen architecture's explicit "explainability by construction" goal.

**3. Dependencies:** M2 (investigation CRUD), M4 (agent start/complete log events), M7 (synthesis/critic events) — effectively the last milestone in the sequence because it consumes signal from all of them.

**4. Repository structure:** extends `app/api/v1/investigations.py` only.

**5. Files to create:** `app/api/v1/investigations_stream.py`, `tests/test_investigations_stream.py`.

**6. Files to modify:** `app/api/v1/investigations.py` (mount the stream route), `orchestrator/graph/builder.py` (ensure every node emits a structured event to a per-investigation pub/sub channel, not just a log line — logs and stream events are related but not identical: logs are for operators, the SSE stream is the same information reshaped for the end user).

**7. Public interfaces:** the SSE endpoint from §2, plus internally:
```python
async def publish_event(investigation_id: UUID, event: InvestigationEvent) -> None: ...
async def subscribe(investigation_id: UUID) -> AsyncIterator[InvestigationEvent]: ...
```

**8. Internal classes:** `InvestigationEvent` (typed union matching the SSE event catalog in §2), implemented via Redis pub/sub (`cache/client.py` from M1 — direct reuse, no new infra), keyed via `RedisKeyBuilder`'s existing namespacing.

**9. Data flow:**
```
Every graph node (M2–M8) → publish_event(investigation_id, event) [fire-and-forget, non-blocking]
Client → GET /investigations/{id}/stream → subscribe(investigation_id) → SSE-formatted event stream
```

**10. Sequence (text):**
```
Client -> API: GET /investigations/{id}/stream
API -> Redis: SUBSCRIBE gaiaos:events:{id}
loop for each graph event
  Graph Node -> Redis: PUBLISH gaiaos:events:{id} {event}
  Redis -> API: event
  API -> Client: SSE event
end
Graph -> Repository: update_status(complete)
Graph -> Redis: PUBLISH ... {event: done}
API -> Client: SSE done event
API -> Client: [close stream]
```

**11. Error handling:** client disconnect mid-stream → server-side subscription cleanly unsubscribes (no leaked Redis subscriptions) — tested explicitly, since leaked pub/sub subscriptions are a classic slow-drip resource leak. If Redis pub/sub is unavailable, the stream endpoint returns a clear `503` (`checkpointer_unavailable`-style error code) rather than hanging open — and the client is expected to fall back to polling (§2's documented fallback path), which doesn't depend on Redis pub/sub at all, only on the `investigations` table.

**12. Logging requirements:** subscribe/unsubscribe events logged with `investigation_id`, `duration_connected_s` — useful operational signal for understanding real client streaming behavior once this is live.

**13. Testing strategy:** Unit — `InvestigationEvent` union type validation. Integration — full SSE stream consumed by a test client for a real (mocked-agents) investigation run, asserting the exact expected event sequence (`planning → agent_started → agent_completed → synthesizing → critic_flag? → done`). Failure-path — Redis pub/sub down → asserts `503`, and separately asserts the polling endpoint (`GET /investigations/{id}`) still works correctly even while streaming is degraded (proves the fallback is real, not just documented). Edge case — client connects to the stream *after* the investigation already completed → must receive a synthetic immediate `done` event with the final state, not hang waiting for events that already happened.

**14. CI impact:** SSE testing requires an async test client capable of consuming a streaming response (`httpx.AsyncClient` supports this) — no new CI infra, but worth flagging as the first "streaming response" test pattern in the codebase, documented for reuse.

**15. Documentation impact:** `docs/phase2/streaming_api.md` — full event catalog (already drafted in §2), reused directly as the doc's content once implemented.

**16. Definition of Done:** a client can submit a query and watch real node-by-node progress via SSE for a full multi-agent investigation, with graceful fallback to polling proven under a simulated Redis outage — this is the "explainability by construction" claim made real and testable, not just architecturally implied.

**17. Risks:** the late-subscriber edge case (client connects after completion) is the one genuinely tricky correctness case in this milestone — budget explicit design/test time for it, since it's the kind of gap that's invisible in a demo (where you always connect before submitting) and only surfaces with real, imperfect client behavior.

**18. Future extensibility:** the same `publish_event`/`subscribe` pair is reusable as-is for any future client type (a second frontend, an admin dashboard watching all in-flight investigations) — nothing about it is coupled to the specific SSE transport, so a future WebSocket or long-poll consumer could subscribe to the same channel without touching graph code.

---

## 5. End Result

### 5.1 Phase 2 Milestone List
1. Redis Connection Layer + Evaluation Harness Foundation
2. Orchestrator Schemas, Episodic Log, Graph Skeleton, Trivial-Path Supervisor + Air Quality Agent
3. Adaptive Planner: Complexity Classifier + Conditional Routing
4. Remaining Domain Agents (Seismic, Ocean, Atmosphere, Wildfire) + Seismic MCP Server + Async Fan-Out
5. Literature/RAG Agent + pgvector + Hybrid Retrieval + Literature MCP Server
6. Causal Chain Agent (Postgres Recursive CTE)
7. Synthesis + Critic (Single-Pass)
8. Simulation Agent (Statistical, Planner-Gated)
9. SSE Streaming, Polling Hardening, Explainability Trace Rendering

### 5.2 Dependency Graph
```
M1 (Redis + Eval Harness)
  │
M2 (Schemas + Episodic Log + Trivial Graph + Air Quality Agent)
  │
M3 (Adaptive Planner routing)
  │
M4 (Seismic/Ocean/Atmosphere/Wildfire + Seismic MCP + Fan-Out)
  │         │
  │         └── M5 (Literature/RAG + Literature MCP)
  │                   │
  └── M6 (Causal Chain) ┘
              │
        M7 (Synthesis + Critic)
              │
        M8 (Simulation, planner-gated)
              │
        M9 (SSE Streaming)
```
Note: M5 and M6 both only depend on M2–M4's fan-out mechanism (not on each other), so they can be built in either order or in parallel across two engineers — the only hard sequential spine is M1→M2→M3→M4→M7→M8→M9, with M5/M6 as a parallel branch that must both complete before M7.

### 5.3 Recommended Implementation Order
As numbered above (1→9), with the explicit option to parallelize M5/M6 if more than one engineer is available. M4 is the one milestone worth considering splitting into 4a (Seismic+MCP+fan-out mechanism) / 4b (Ocean/Atmosphere/Wildfire) if a single engineer needs a natural pause point — flagged in M4's own Risks section already.

### 5.4 Postponed to Phase 3
- Neo4j migration (only if `hazard_relationships` scale or query-pattern needs actually materialize — trigger already documented in the frozen architecture, not re-litigated here).
- Bounded Critic replan loop (explicitly deferred by the frozen architecture until the eval harness has enough real signal to measure whether it helps).
- Remaining MCP server wrappers beyond Seismic/Literature (only if a second real MCP client consumer materializes).
- Real authentication (`AuthStub` replacement) and the `investigations.user_id` column that depends on it.
- Real rate limiting (`RateLimitStub` replacement), reusing the `RedisKeyBuilder` namespace already reserved for it in M1.
- Kafka/Kubernetes migration triggers (unchanged from the frozen architecture — still not needed, still documented, still not Phase 2 or Phase 3 work unless the documented triggers actually fire).
- Cost/latency dashboards beyond what the eval harness's `eval_benchmark_runs.metrics` JSONB already captures — a dedicated observability UI is real future work, not assumed here.

### 5.5 Intentionally Excluded (not just postponed — explicitly out of scope)
- A general-purpose plugin system for adding new domain agents dynamically at runtime — every agent in Phase 2 is added by writing code and a migration, not by a config-driven plugin loader. This matches the frozen architecture's "add a node when you add a domain" philosophy explicitly, and a runtime plugin system would be exactly the kind of speculative infrastructure the original architecture review correctly rejected Kafka/K8s for.
- Multi-tenancy / per-organization data isolation — no signal in the frozen architecture or Phase 1 that this is a near-term requirement; introducing it now would be premature schema design for a requirement that doesn't exist yet.
- A physics-based simulation engine — explicitly and repeatedly rejected across every document in this project's history; restated here only to be unambiguous it's not quietly Phase 3 work either, it's off the table absent a real, separately-justified reason to revisit the original v1.0 ruling.

### 5.6 Final Architecture Review

Walking the dependency graph in §5.2 forward exactly as written: M1 gives every later milestone a working cache/checkpoint backend before anything needs one. M2 gives every later agent a contract to implement and a place to durably log progress before any agent writes its first line of business logic. M3 gives M4 somewhere real to route to before a second agent exists, so "every query hits every agent" is never briefly true as an intermediate state. M4 and M5 both ship their MCP wrappers in the same milestone as the agent they belong to, so there's no future milestone rewriting tool-calling code that already works. M6 is fully decoupled from M5 and only needs M4's fan-out mechanism, confirmed independently mergeable. M7 is the first milestone requiring evidence from multiple prior milestones, sequenced correctly as the point where they need to already exist, not before. M8 depends on M3's classifier extension and M7's uncertainty-bounds schema field — both are prerequisites already satisfied by the point M8 starts, not discovered mid-milestone. M9 consumes log/event signal that every prior milestone was already required to emit (M2 established the pattern, M4/M7/M8 each restated "logging requirements" that feed it) — nothing in M9 requires retrofitting event emission into milestones that already shipped.

### 5.7 Self-Review Pass

**Question:** if this were implemented exactly as written, would missing architecture surface halfway through?

Checked specifically for: schema changes needed by a later milestone but not designed until then (resolved — all four new tables are designed up front in §3, attached to the earliest milestone that needs them, not the milestone that merely uses them most visibly); an interface invented twice (resolved — `AgentInput`/`AgentOutput` is defined once in M2 and never re-derived; the URL-rewrite-duplication mistake from the Phase 1 audit was checked for and not repeated — `RedisKeyBuilder` and `CitationMapper` are each defined once and imported, not reimplemented per-consumer); a milestone that needs infrastructure introduced later (resolved via the four pre-flight fixes in §0 — Redis-before-graph, schemas-before-first-agent, episodic-log-before-first-agent, MCP-alongside-its-agent); and a milestone whose "Definition of Done" secretly depends on a capability from a *later* milestone (checked each DoD against its own Dependencies list — none found; M7's DoD explicitly only claims what M2–M6 can supply, M9's DoD explicitly depends on event emission that M2/M4/M7/M8 were each already required to implement as part of their own scope, not deferred).

**Answer: No.** The architecture as sequenced above does not require revision. Proceed to Milestone 1.
