# GaiaOS Architecture v1.0 — Final Architectural Decision

**Role:** Chief Architect / Distinguished Engineer sign-off
**Inputs reviewed:** Original architecture proposal, Independent Staff Engineer review
**Status:** Final — supersedes both prior documents

---

## 0. Overall Verdict

**Final Architecture Score: 8.7/10** (see §12 for scoring breakdown and why this is *lower* than the reviewer's 9.2)

The original proposal's core call — reject Kafka, reject K8s, choose the orchestrated multi-agent graph — is correct and I'm not revisiting it. That decision was made on the right basis: what problem does GaiaOS actually have (reasoning-quality bottleneck, not throughput), not what infra looks impressive. Both documents agree here, and so do I.

Where I differ from *both* prior documents: this is being built by **one engineer**, and neither document treats that as a hard constraint on scope — it treats it as a footnote. The Staff Engineer review correctly flags several things as premature, but then adds two *new* mandatory components (Adaptive Planner, Evaluation Framework) without cutting anything to pay for them. A real staff-eng sign-off has to make the budget balance. Below, every "keep" is paid for by something being cut, deferred, or shrunk. That trade-off accounting is the actual job here, and it's what I'm adding that neither document did.

---

## 1. Point-by-Point Rulings on Every Disputed Decision

### 1.1 Neo4j — **RULING: Defer to v2. Reviewer 2 is right, and for a sharper reason than given.**

Original: keep, narrowly scoped to the causal/correlation graph.
Reviewer 2: maybe — depends whether GaiaOS "truly depends" on graph traversal.

My reasoning goes further than either: the real question isn't whether graph traversal is *useful* (it obviously is for causal-chain reasoning — that's genuinely graph-shaped data). The question is whether the **v1 causal knowledge graph will have enough populated data to make Neo4j's traversal advantage matter.** A knowledge graph of historical hazard events that a solo engineer seeds in the first few weeks will have, realistically, dozens to low hundreds of nodes. At that size, Postgres recursive CTEs are not just "adequate" — they are *faster to build, faster to debug, and indistinguishable in query latency* from Neo4j. The advantage Neo4j has (multi-hop pattern queries at scale) doesn't exist yet because the scale doesn't exist yet.

Running a second stateful database for a graph that fits in a Postgres table with a `parent_event_id` and a join table is the same mistake as the rejected Qdrant-vs-pgvector call, just not caught the first time. **Apply your own framework consistently.**

- v1: `hazard_events`, `hazard_relationships` tables in Postgres, recursive CTE for chain traversal, capped at a small max depth (e.g. 4 hops) — which covers essentially every real causal-chain question this system will be asked.
- Migration trigger to Neo4j: graph exceeds ~50k nodes **or** you need pattern-matching queries (not just path traversal) that recursive CTEs genuinely can't express cleanly — e.g., "find all triads of event types occurring within N days regardless of order."
- This also removes an entire deployment, backup story, and Cypher-vs-SQL context switch from a one-person project. That's a real cost saved, not a theoretical one.

### 1.2 MCP — **RULING: Partial keep. Neither reviewer's position as stated.**

Original: keep, scoped to all external science-data tools.
Reviewer 2: postpone entirely to v2.

Both are half right. Reviewer 2's core point stands: with one backend and one frontend, MCP's *reusability* value is currently theoretical. But there's a cost asymmetry the reviewer missed: **you are wrapping these external APIs in typed tool schemas either way.** The domain agents need `get_recent_earthquakes(region, min_magnitude, since)` as a typed function regardless of whether it's exposed over MCP or called directly. MCP's marginal cost, once you already have the typed wrapper, is a thin protocol server — not a second implementation.

So the real decision isn't "MCP or not," it's "expose the thin protocol layer on top of tools you're building anyway, or don't."

- **v1:** Build every tool as a plain typed Python function first (this is the wrapper you need regardless). Wrap **two** of them — Seismic (USGS) and Literature Search — as actual MCP servers. This proves the pattern works, is directly demoable to a Claude Desktop client (real portfolio value — "I built an MCP server Claude Desktop can use" is a concrete, verifiable claim), and costs maybe a day of extra work.
- **v2:** Wrap the remaining tool servers only if a second consumer (analyst IDE tool, second app) actually materializes. Don't wrap them speculatively.

This is cheaper than the original's "wrap everything" and more useful than the reviewer's "wrap nothing."

### 1.3 Critic/Verifier recursion — **RULING: Reviewer 2 is correct. Single pass for v1.**

The original's "Critic can trigger a replan" is explicitly listed as its own *future work*, not core v1 scope — so this disagreement is smaller than it looks. Reviewer 2's proposed simplification (one verification pass, no loop) is just enforcing what the original already flagged as out-of-scope for v1. I'm ratifying that, and closing the ambiguity: **no replan loop in v1, full stop.** A bounded 2-cycle replan is a v1.1 feature added *after* the evaluation harness exists to measure whether it actually improves answer quality — because an unmeasured self-correction loop is exactly the kind of feature that looks impressive and might make answers worse (over-hedging, thrashing between agents) with no way to know.

### 1.4 Simulation Agent mandatory vs. planner-driven — **RULING: Reviewer 2 is correct, no dispute.**

Making Simulation mandatory on every query is both a cost problem and a quality problem — a simple "current AQI in Delhi" query doesn't need a wildfire-spread cellular automaton anywhere near it. This folds directly into §1.6 (Adaptive Planner). Also ratifying the original's own caution here: statistical/existing environmental models, not a from-scratch physics engine. A solo engineer building a physics simulator is a multi-month distraction from the actual thesis of the project (reasoning + explainability).

### 1.5 Kafka / Kubernetes — **RULING: No dispute. Both correctly rejected for v1.**

Both documents agree, I agree, nothing to add except: the original's documented migration triggers (§3.11) are good and should be kept verbatim as the v2+ scaling doc — a real staff engineer wants to see *that* you know when to introduce this complexity, not just that you avoided it now.

### 1.6 Adaptive Planner — **RULING: Adopt. This is the single best addition in the review.**

This is the correct fix to the cost/latency problem the reviewer separately (and correctly) identifies in §15 of their review. Rather than treating "cost optimization" and "adaptive planner" as two separate line items, they're the same fix: **the planner's job is not just decomposition, it's triage.** Concretely:

- Supervisor classifies query complexity at intake (cheap, fast classification step — can be a small/fast model call, not the main reasoning model) into: `trivial` (single-domain factual lookup), `moderate` (2–3 domains, no simulation), `complex` (multi-domain + simulation + causal graph).
- Graph has a genuine conditional edge (not a hack, as the original correctly notes LangGraph-style graphs support this natively) that skips Simulation, Causal Graph, and even multi-agent fan-out entirely for `trivial` queries — those short-circuit to a single domain agent → direct response, bypassing Synthesis/Critic overhead where it isn't needed.
- This single change is the honest fix for both the reviewer's cost complaint and the "8-step pipeline sounds slow" critique the original already anticipated but didn't resolve.

### 1.7 Evaluation Framework — **RULING: Adopt, and reorder the build plan around it.**

The reviewer is right that this was the biggest gap, and — credit where due — the original document *already diagnosed this itself* in its own closing paragraph ("I'd reverse that build order... build the eval harness first"). So this isn't really a disagreement, it's ratifying the original's own admitted regret and actually acting on it instead of listing it as a nice-to-have. This is why the Milestone Plan below puts the eval harness at **Milestone 1**, not last.

Concrete metrics (the reviewer listed categories; here are the actual measurable definitions):
- **Retrieval precision**: for a fixed benchmark set, % of literature citations that a human reviewer marks as actually relevant to the claim they support.
- **Agent success rate**: % of domain-agent tool calls that return usable (non-error, non-empty) evidence.
- **Confidence calibration**: bucket Critic-assigned confidence scores, compare against human-judged correctness rate per bucket (a real calibration curve, not just "we have confidence scores").
- **Cost/latency per complexity tier**: tracked separately for trivial/moderate/complex, since a single blended average hides the Adaptive Planner's actual effect.

---

## 2. What I'm Overruling in Both Documents

- **The reviewer's implicit claim that adding Adaptive Planner + Eval Framework is "free" on top of everything else the original proposed.** It isn't, for one engineer. I'm paying for both by cutting Neo4j and most of MCP from v1 (§1.1, §1.2). The reviewer never named this trade-off explicitly; I am.
- **The original's 6-domain-agent fan-out as the default path for every query.** Correct as the *ceiling* of what the system can do, wrong as the *default*. §1.6 fixes this.
- **The score of 9.2/10.** Score is for the architecture *as scoped for v1 implementation by one person*, not the architecture as an abstract diagram. As an abstract diagram it's a 9+. As a thing one engineer ships in a bounded timeline, unscoped, it was heading toward a 7 (over-committed, under-sequenced). The rulings above bring the *implementable* version back up — see §12.

---

## 3. Final Technology Stack

| Technology | Verdict | Scope | Notes |
|---|---|---|---|
| PostgreSQL + PostGIS | **KEEP** | System of record, structured/geospatial data, causal event chains (recursive CTE) | Also absorbs the v1 "knowledge graph" role |
| pgvector | **KEEP** | RAG over papers/reports | Right-sized to actual corpus |
| Neo4j | **DEFERRED to v2** | Causal graph, if scale/pattern-query needs emerge | Trigger: >50k nodes or need for pattern (not path) queries |
| Redis | **KEEP** | Cache, ephemeral agent state, checkpointing, task queue | Uncontroversial |
| Kafka | **REJECTED** | — | Ingestion cadence doesn't need it; documented v2+ trigger |
| Kubernetes | **REJECTED for v1** | — | Managed container platform sufficient; documented v2+ trigger |
| Docker | **KEEP** | Packaging | Independent of orchestrator choice |
| LangGraph-style orchestrator | **KEEP** | Control flow, checkpointing, conditional/adaptive edges | Now also carries Adaptive Planner logic |
| MCP | **KEEP, narrowed further** | 2 tool servers only in v1 (Seismic, Literature) | Rest as plain typed functions until a second client exists |
| Object storage (S3-compatible) | **KEEP** | Imagery, rasters, report artifacts | Uncontroversial |

---

## 4. Final Agent Architecture

```
Client
  │
API Gateway (AuthN/Z, rate limit)
  │
Orchestrator (state graph)
  │
  ├─ Supervisor / Adaptive Planner
  │     classifies query complexity → chooses execution path
  │
  ├─ [trivial path]  →  1 Domain Agent  →  direct response
  │
  └─ [moderate/complex path]
        │  async fan-out
        ├─ Seismic Agent
        ├─ Ocean Agent
        ├─ Atmosphere Agent
        ├─ Wildfire Agent
        ├─ Literature/RAG Agent
        ├─ Causal Chain Agent (Postgres recursive CTE, not Neo4j in v1)
        └─ Simulation Agent  (only if planner marks query as needing prediction)
        │  fan-in
        ├─ Synthesis Agent  (evidence-backed answer + citation map)
        └─ Critic Agent     (single verification pass, v1 — no replan loop)
        │
        Response + execution trace
```

Every domain agent keeps its narrow scope and own tool subset — that design was correct in the original and unchanged here. The only structural addition is the complexity-classification branch at the top and the removal of the Critic's recursive loop.

---

## 5. Final Data Flow

1. **Intake** — query hits gateway, authenticated, routed to Orchestrator.
2. **Classify** — Supervisor tags complexity (trivial/moderate/complex) using a fast, cheap model call.
3. **Plan** — task graph built; for trivial queries this is a single node.
4. **Gather** — domain agents run async, hit MCP servers (Seismic, Literature) or direct typed tool calls (everything else), cache through Redis, write structured results to Postgres.
5. **Reason** — Causal Chain Agent runs recursive CTE query if relevant; Simulation Agent runs only if planner flagged prediction need.
6. **Synthesize** — Synthesis Agent merges evidence into a claim-by-claim answer with a citation map.
7. **Verify** — Critic checks each claim against evidence once; flags (not blocks) unsupported claims.
8. **Respond** — answer + execution trace streamed to client via SSE; full trace logged to Postgres episodic store for the eval harness.

---

## 6. Final Deployment Strategy

- Managed container platform (Cloud Run/App Runner/ECS Fargate-class) for: API Gateway, Orchestrator, the 2 MCP tool servers, Simulation service.
- Managed Postgres (PostGIS + pgvector extensions), managed Redis, managed object storage. **No managed Neo4j in v1.**
- Scheduled ingestion via Celery beat / cloud scheduler, not Kafka.
- Terraform for infra-as-code; standard CI/CD container pipeline.
- dev/staging/prod, with staging using cached fixtures for external hazard APIs (avoid burning free-tier rate limits).
- Migration path to Neo4j/Kafka/K8s documented explicitly (kept from the original almost verbatim — it was already correct) as a v2+ appendix, not a v1 task.

---

## 7. Final Folder Structure

```
gaiaos/
├── gateway/
├── orchestrator/
│   ├── graph/                 # state graph, adaptive routing, checkpointing
│   ├── agents/
│   │   ├── supervisor/        # includes complexity classifier
│   │   ├── seismic/
│   │   ├── ocean/
│   │   ├── atmosphere/
│   │   ├── wildfire/
│   │   ├── literature_rag/
│   │   ├── causal_chain/      # Postgres recursive CTE, not Neo4j
│   │   ├── simulation/
│   │   ├── synthesis/
│   │   └── critic/
│   └── schemas/                # typed I/O contracts, checked at graph-build time
├── mcp_servers/
│   ├── seismic_usgs/           # actual MCP server
│   └── literature_search/      # actual MCP server
├── tools/                      # plain typed function wrappers for everything else
│   ├── ocean_noaa/
│   ├── weather/
│   ├── air_quality_openaq/
│   └── wildfire_firms/
├── simulation_engine/
├── ingestion/
├── data/
│   ├── migrations/             # Postgres + PostGIS + pgvector + causal-chain schema
├── prompts/                    # separated from code, per-agent
├── eval/
│   ├── benchmarks/              # curated question/evidence/answer sets
│   ├── metrics/                 # retrieval precision, calibration, success rate
│   └── harness/                 # re-run against every orchestrator/prompt version
├── infra/                      # Terraform, CI/CD
└── future/                     # documented Neo4j/Kafka/K8s migration triggers
```

---

## 8. Final Milestone Plan (implementation order)

1. **Eval harness + benchmark question set** — before any agent is built. This is the one reordering that matters most; nothing after this milestone ships without a way to detect regression.
2. **Postgres/PostGIS schema + one domain agent (pick the simplest, e.g. Air Quality) + Supervisor trivial-path only** — proves the skeleton end-to-end on the cheapest possible path.
3. **Adaptive Planner complexity classifier** — added once you have ≥2 domain agents to route between.
4. **Remaining domain agents (Seismic, Ocean, Atmosphere, Wildfire)** — parallel fan-out, async tool calls, Redis caching.
5. **Literature/RAG agent + pgvector + hybrid BM25 fusion.**
6. **Causal Chain agent (Postgres recursive CTE).**
7. **Synthesis + Critic (single-pass).**
8. **Simulation agent (statistical models only), planner-gated.**
9. **2 MCP server wrappers (Seismic, Literature) + SSE streaming/explainability trace to client.**
10. **v1.1 stretch, only after eval harness shows a baseline:** bounded Critic replan loop.

## 9. Estimated Timeline (one engineer, part-time-realistic)

- Milestones 1–2: 2–3 weeks
- Milestones 3–5: 3–4 weeks
- Milestones 6–8: 3–4 weeks
- Milestone 9: 1–2 weeks
- **Total v1: roughly 10–13 weeks** of consistent part-time work to a genuinely demoable, defensible system — not a weekend project, and not a 6-month one either.

---

## 10. Missing Components Now Added

- Eval harness (moved to Milestone 1, not an afterthought)
- Adaptive/cost-aware planner (moved to Milestone 3, not a stretch goal)
- `prompts/` as a first-class, version-controlled folder separate from code

## 11. Simplifications Made

- Neo4j → Postgres recursive CTE for v1
- MCP → 2 servers instead of 8
- Critic → single pass, no recursion, in v1
- Simulation → planner-gated, not mandatory

## 12. Final Architecture Score: **8.7/10**

- Innovation: 9/10 — Adaptive Planner + explainability-by-construction is a genuinely good idea, not just decoration.
- Engineering judgment: 9/10 — the technology-elimination discipline (reject Kafka/K8s/Neo4j-for-now/most-of-MCP) is the strongest part of this whole exercise, and it's consistently applied now, not just in the parts that were flashy to reject.
- Feasibility for one engineer: 8.5/10 — realistic once scoped as above; would have been 6/10 unscoped.
- Resume/portfolio impact: 9.5/10 — a working system with a real eval harness and a documented "here's what I cut and why" story is more impressive to an actual staff engineer than a bigger diagram with no eval and no adaptive routing.
- Deducted for: even the trimmed v1 is still a lot of surface area (9 agent modules + eval harness + 2 MCP servers) for one person on a 10–13 week timeline — the honest risk is scope creep back toward the original's fuller vision before Milestone 1 is even done. Guard against that explicitly, not implicitly.
