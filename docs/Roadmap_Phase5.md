# GaiaOS — Phase 5 Engineering Design Document

**Role:** Principal Software Architect / Distributed Systems Architect / AI Systems Architect / Platform Architect, designing for a five-year horizon.
**Status:** Phases 1–4 and Open Source Readiness (v4.1–v4.4) complete and frozen. Nothing below redesigns them except where named explicitly as unavoidable.
**Mission shift:** Phases 1–4 built the platform. Phase 5 builds the intelligence the platform exists to deliver. Every milestone below is judged against one question: does this make GaiaOS reason better, more honestly, and more collaboratively — not just run more reliably.

---

## Part A — Architectural Review Before Milestone 1

### A.1 Bounded Contexts (as they actually exist today, made explicit for the first time)
GaiaOS has never formally named its bounded contexts; it has consistently *behaved* as if they existed, which is why four phases of independent milestone work never produced real coupling problems. Naming them now is documentation of a fact, not a redesign:

1. **Reasoning Core** — `orchestrator/` (graph, agents, schemas). Owns: task decomposition, agent execution, synthesis, verification. Speaks to everything else only through typed contracts (`AgentInput`/`AgentOutput`, `Evidence`).
2. **Evidence & Retrieval** — literature/RAG, causal chain, hazard data. Owns: what counts as evidence and how it's found.
3. **Evaluation & Quality** — `eval/`. Owns: what counts as *correct*, and whether the system is getting better or worse over time. Currently the weakest context, per the Phase 4 audit's Critical finding — this is Phase 5's first job to fix.
4. **Platform Services** — `auth/`, `gateway/`, `cache/`, `workers/`, `metrics/`, `alerting/`. Owns: identity, durability, observability. Deliberately boring, deliberately stable.
5. **Data & Ingestion** — `ingestion/`, `tools/`, `db/models/hazard_event.py`. Owns: how the outside world's data gets into the system honestly.
6. **Extensibility** — `mcp_servers/`, `scripts/new_agent_template/`, `docs/CONTRIBUTING_AGENTS.md`. Owns: how someone who isn't the core team adds capability.

### A.2 Architectural strengths to preserve, not touch
The Protocol-based interface pattern (auth, rate limiting, notification channels), the scheduler-job idiom (ingestion, alerting, backups), and the typed-contract discipline (`AgentInput`/`AgentOutput`/`Evidence`) have each been reused three or more times across four phases without strain. This is the load-bearing architectural asset of the entire project. Phase 5's plugin architecture (M6) and multi-agent collaboration protocol (M4) must extend these patterns, not replace them.

### A.3 Hidden coupling found on this review
**The Evaluation & Quality context has been silently non-functional since Phase 2.** `calculate_calibration()` and `calculate_retrieval_precision()` returning a hardcoded `0.0` means every other context that *thinks* it has a quality signal to lean on — the Critic replan loop's still-unconfirmed A/B measurement, any future SLO (M8), any future plugin agent's eval-gate check (M6) — has actually been coupled to a constant, not a real metric, without anyone downstream knowing it. This is the single most important thing to fix before building anything else in this phase, and it is why it is Milestone 1, not a footnote.

### A.4 Future migration risks named now, not built now
- **Neo4j** — trigger (>50k causal-graph nodes, or genuine pattern-query need) still not met. Re-check at Phase 5 exit, not before.
- **A dedicated vector DB (Qdrant)** — trigger (>10–20M literature chunks) still not met.
- **True Kubernetes-based autoscaling** — Phase 4's advisory scaling policy has not yet produced enough real `recommended_pool_size` data to justify building an actuator on top of it; Phase 5's M7 checks this data before deciding, exactly as Phase 4 designed it to.

### A.5 Where this document *does* deliberately extend prior decisions
Two, both justified against real, new evidence rather than speculation:
1. **A genuine plugin architecture (M6)**, evolving Phase 4's static contribution-framework-plus-CI-check into dynamic-loadable agents. This was explicitly rejected as premature in Phase 2 and Phase 3. It is justified now because the static contract has survived four phases and a real external-contribution framework unchanged — the thing that would have made a plugin system premature (an unstable contract) is the thing that's now proven stable.
2. **A public research-facing API and dataset (M9)**, because Phase 5's stated mission — "a production-grade planetary intelligence system" — is not fully true of a system whose intelligence output only its own operators can see. This is scoped narrowly (read-only, aggregated, SLO-backed) specifically to avoid repeating the "build it because it sounds right" mistake this project has consistently and correctly avoided elsewhere.

---

## Part B — System Architecture

### B.1 Subsystem Ownership Diagram
```
                    ┌─────────────────────────┐
                    │   Public Research API     │  (M9 — new, read-only, external)
                    └────────────┬──────────────┘
                                 │
┌────────────────────────────────┼────────────────────────────────┐
│                          Reasoning Core                          │
│   Supervisor → [Agent Collaboration Bus] → Synthesis → Critic    │
│                        (M4 adds the bus)                          │
└──────┬──────────────────┬──────────────────┬──────────────────┬──┘
       │                  │                  │                  │
┌──────▼──────┐  ┌────────▼────────┐  ┌──────▼──────┐  ┌────────▼────────┐
│  Evidence &  │  │   Extensibility  │  │  Evaluation │  │ Platform Services│
│  Retrieval   │  │  (M6 — plugin    │  │  & Quality  │  │ (auth, workers,  │
│ (+ M5 cross- │  │   loader)        │  │  (M1 — real  │  │  metrics, alert) │
│  domain)     │  │                  │  │   metrics)   │  │                  │
└──────┬───────┘  └──────────────────┘  └──────┬──────┘  └──────────────────┘
       │                                        │
┌──────▼──────────────────────────┐    ┌────────▼────────┐
│      Data & Ingestion            │    │  SLO/Error Budget│
│                                   │    │  Layer (M8)       │
└───────────────────────────────────┘    └───────────────────┘
```

### B.2 Event Contracts (new in Phase 5)
Phase 4 had one event bus (Redis pub/sub, SSE-facing, per-investigation progress). Phase 5 introduces a second, deliberately separate one: an **internal agent-collaboration channel** (M4), scoped strictly within a single investigation's fan-out lifecycle, never crossing investigation boundaries, never exposed externally. Two buses, two purposes, no shared schema — collaboration events are not progress events, and conflating them (making SSE consumers parse inter-agent chatter, or making inter-agent messages carry UI-display concerns) would be exactly the kind of hidden coupling this review is watching for.

### B.3 Internal vs. Public APIs
- **Internal:** `AgentInput`/`AgentOutput`/`Evidence` (Reasoning Core ↔ Evidence & Retrieval), the new `CollaborationMessage` contract (M4, Reasoning Core internal only), the `PluginManifest` contract (M6, Extensibility ↔ Reasoning Core).
- **Public:** `/api/v1/*` (existing, unchanged contract), `/api/v1/research/*` (M9, new, additive, versioned identically to the existing policy).

---

## Part C — Milestones

### Milestone 1 — Real Confidence Calibration & Retrieval Precision

**1. Goal:** Implement `calculate_calibration()` (expected calibration error) and `calculate_retrieval_precision()` (relevant-retrieved overlap) for real, replacing the three-phase-old `return 0.0` placeholders.
**2. Engineering motivation:** every quality claim this project has made or will make is currently unverifiable; this is the root of Part A.3's hidden coupling.
**3. Dependencies:** none — root milestone.
**4. Architectural rationale:** these are pure functions living in `eval/metrics/`, already correctly isolated from the rest of the system; fixing them is a scoped, low-blast-radius change to two files plus their call sites.
**5. Scope:** the two named functions, their wiring into `eval/harness/runner.py`'s scoring, and a backfill re-score of the existing 18-question benchmark history so there's a real baseline the moment this ships.
**6. Out of scope:** changing the benchmark question set itself, changing the eval-gate CI threshold logic (Phase 3's `check_for_regression` continues to work unchanged, now against real numbers instead of constant zeros).
**7. Repository impact:** `eval/metrics/{calibration,retrieval_precision}.py` rewritten; `eval/harness/scorer.py` modified to pass real inputs (predicted confidence + actual correctness for calibration; retrieved-chunk-IDs + relevance-judgment set for precision).
**8. New modules:** `eval/metrics/relevance_judgments.py` — a small, explicit, hand-curated relevance-judgment set per literature-heavy benchmark question (required input for retrieval precision; doesn't exist yet, since the metric never actually ran).
**9. Modified modules:** `eval/harness/runner.py`, `eval/harness/scorer.py`.
**10. Public interfaces:**
```python
def calculate_calibration(predictions: list[tuple[float, bool]], n_bins: int = 10) -> float:  # ECE
def calculate_retrieval_precision(retrieved_ids: list[UUID], relevant_ids: set[UUID]) -> float:
```
**11. Internal interfaces:** `RelevanceJudgment(question_id, relevant_evidence_ids)`.
**12. Data flow:** `eval run completes → scorer collects (confidence, correct) pairs across all questions → calculate_calibration(pairs) → ECE stored on the BenchmarkSuiteResult; per literature-question, scorer collects retrieved evidence IDs → compares against RelevanceJudgment → calculate_retrieval_precision`.
**13. Sequence (text):**
```
Harness -> Scorer: score(question, investigation_result)
Scorer -> calculate_calibration: (all confidence/correctness pairs so far)
Scorer -> calculate_retrieval_precision: (retrieved_ids, relevance_judgments[question_id])
Scorer -> BenchmarkSuiteResult: attach real ece, real precision
Harness -> Postgres: INSERT eval_benchmark_runs [now with real numbers]
```
**14. Database impact:** none — same table, real values instead of placeholders.
**15. Redis impact:** none.
**16. Background workers:** none new — runs inside the existing nightly eval-gate job.
**17. LangGraph impact:** none.
**18. Evaluation impact:** this milestone *is* the evaluation-system fix.
**19. Security impact:** none.
**20. Observability:** `eval.calibration.ece`, `eval.retrieval.precision` become real, trend-able metrics for the first time — wire into M8's SLO layer later, not this milestone.
**21. Metrics:** as above.
**22. Performance:** negligible — computed once per nightly eval run, not per-request.
**23. Scalability:** none.
**24. Reliability:** a bad ECE/precision calculation must not crash the eval run — wrap in the same try/log/continue pattern already used for individual question failures.
**25. Error handling:** a question with no relevance judgments defined → precision calculation skipped for that question with an explicit "no judgment set" marker, not silently scored 0 or 1.
**26. Testing strategy:** unit tests against textbook ECE examples with known correct answers (this is a well-defined statistical quantity — testable against ground truth, not just "runs without error"); unit tests for precision against hand-constructed retrieved/relevant sets.
**27. CI/CD impact:** the eval-gate workflow now fails/passes on real numbers — worth a one-time manual review of the first real nightly run's output before trusting the gate's judgment automatically.
**28. Documentation impact:** `docs/phase5/eval_metrics.md` — the ECE formula, the relevance-judgment curation process (who defines them, how they're kept current as new benchmark questions are added).
**29. Migration strategy:** none (no schema change).
**30. Rollback strategy:** revert to the constant-zero functions if a real formula bug is found post-merge — trivial, one-file revert.
**31. Definition of Done:** ECE unit tests pass against known statistical fixtures; a full nightly eval run produces non-zero, plausible ECE and precision values; the Phase 4-audit-flagged finding is closed with a written before/after comparison.
**32. Risks:** relevance-judgment curation is a real, ongoing content burden, not a one-time task — flagged honestly, not hidden.
**33. Technical debt intentionally accepted:** relevance judgments initially cover only the literature-heavy benchmark questions (a handful of the 18) — full coverage is Phase 5+ backlog, not blocking this milestone.
**34. Future extensibility:** M6's plugin agents will need their own eval coverage (per Phase 4's `agent_contract_check.yml` pattern) — this milestone's real scoring is what makes that check meaningful rather than another silent placeholder risk.

**ADR-501: Expected Calibration Error over Brier Score**
*Decision:* use ECE (binned, standard 10-bin) as the calibration metric.
*Context:* the placeholder never specified a formula; several are standard (Brier score, log loss, ECE).
*Alternatives considered:* Brier score (simpler, single number, but conflates calibration and sharpness — a model that's always 50% confident and right half the time scores identically to a well-calibrated confident model, which is exactly the distinction this system needs to see). Log loss (heavily penalizes confident-wrong predictions, arguably desirable, but harder to communicate to a non-ML-specialist operator reading a dashboard).
*Why ECE wins:* it's directly interpretable ("our stated confidence is off by X on average"), it's the standard metric named in Architecture v1.0's own original phrasing ("expected calibration error"), and it's bin-visualizable on M8's future dashboard work without extra transformation.
*Future implications:* if per-domain calibration (not just system-wide) becomes valuable later, ECE's binned structure supports that extension without a formula change.

---

### Milestone 2 — Repository & Supply-Chain Integrity Closure

**1. Goal:** Close the two remaining named-backlog hygiene items: a CI check that `requirements/base.txt`'s declared ranges still cover what `base.lock` resolves to, and repository-wide `.gitattributes` line-ending normalization.
**2. Engineering motivation:** both are small, both were explicitly named as accepted Phase 5 backlog, both are the kind of thing that's cheap now and a recurring source of contributor confusion if left open indefinitely.
**3. Dependencies:** none — fully parallel to every other Phase 5 milestone.
**4. Architectural rationale:** this mirrors the OpenAPI-drift-check and agent-contract-check patterns already established in Phase 4 — the same "make staleness structurally impossible" idiom applied a third and fourth time, not a new category of engineering.
**5. Scope:** exactly the two named items.
**6. Out of scope:** any other dependency-hygiene item (SBOM, CodeQL, SHA-pinning) — named in prior audits as correctly low-priority, not pulled forward here without new justification.
**7. Repository impact:** `.gitattributes` (new, root), `.github/workflows/dependency-range-check.yml` (new), `requirements/base.txt` (the LangGraph range fixed as part of this milestone, since the check would otherwise fail immediately on merge).
**8. New modules:** `scripts/check_requirements_drift.py`.
**9. Modified modules:** `requirements/base.txt`, `CONTRIBUTING.md` (fix the `dev.txt`/`dev.lock` contradiction flagged in the open-source-readiness audit — the direct, named fix for that finding).
**10. Public interfaces:** none.
**11. Internal interfaces:** `check_requirements_drift.py <package.txt> <package.lock>` — CLI, parses both, asserts every pinned version in the lock satisfies the corresponding range in the source file.
**12. Data flow:** `CI → check_requirements_drift.py base.txt base.lock → pass/fail`.
**13. Sequence (text):**
```
CI -> check_requirements_drift: (base.txt, base.lock)
check_requirements_drift -> parse both files
loop for each package in lock
  check_requirements_drift -> verify lock version satisfies txt range
  alt violated
    check_requirements_drift -> fail: "langgraph==1.0.10 does not satisfy declared range >=0.2.0,<0.3.0"
  end
end
```
**14. Database impact:** none.
**15. Redis impact:** none.
**16. Background workers:** none.
**17. LangGraph impact:** none.
**18. Evaluation impact:** none.
**19. Security impact:** none directly — indirectly closes a supply-chain-hygiene gap.
**20. Observability:** none new.
**21. Metrics:** none new.
**22. Performance:** none.
**23. Scalability:** none.
**24. Reliability:** none.
**25. Error handling:** the check's failure message must name the specific package and versions (per point 13) — a generic failure would be as unhelpful as the problem it's fixing.
**26. Testing strategy:** unit tests against a deliberately-drifted fixture pair (txt says `<2.0`, lock resolves `2.1.0`) asserting the check catches it; unit test against a consistent pair asserting it passes.
**27. CI/CD impact:** new required check on every PR touching `requirements/`.
**28. Documentation impact:** `CONTRIBUTING.md` fix (point 9); a short note in `docs/phase5/` on the drift-check's existence.
**29. Migration strategy:** none.
**30. Rollback strategy:** trivial — remove the CI step.
**31. Definition of Done:** the deliberately-drifted fixture test passes; `CONTRIBUTING.md` and `README.md` now give identical setup instructions, verified by direct comparison.
**32. Risks:** none significant.
**33. Technical debt intentionally accepted:** none — this milestone is itself a debt-closure.
**34. Future extensibility:** the same drift-check pattern applies to `dev.txt`/`dev.lock` and any future requirements-file pair without new design.

---

### Milestone 3 — Uncertainty Estimation Framework

**1. Goal:** Replace ad hoc per-agent `confidence: float` scoring with a principled, consistent uncertainty representation — confidence intervals with an explicit source-of-uncertainty tag (data sparsity, model uncertainty, or evidence conflict), not just a bare number.
**2. Engineering motivation:** Architecture v1.0 named "uncertainty estimation" as a core value proposition from day one (the Simulation agent's "uncertainty bounds," the Synthesis agent's confidence scores); today these are structurally present but semantically inconsistent — a Simulation agent's `uncertainty_bounds` tuple and a Synthesis claim's `confidence: float` aren't expressions of the same underlying concept, and nothing forces them to be comparable.
**3. Dependencies:** Milestone 1 — a "confidence" number is only meaningful once ECE proves whether stated confidence tracks actual correctness; building a fancier uncertainty representation on top of an unverified confidence signal would be building on sand.
**4. Architectural rationale:** this is a schema unification, not a new subsystem — `Evidence.confidence` and `SimulationResult.uncertainty_bounds` both get expressed through one shared `UncertaintyEstimate` type, used consistently across every agent that currently reports confidence its own way.
**5. Scope:** the `UncertaintyEstimate` schema; migrating every existing confidence-emitting agent (all six domain agents, Simulation, Synthesis, Critic) to emit it; Synthesis's citation logic updated to propagate uncertainty through claim aggregation (a claim built from two pieces of evidence with different uncertainty sources should reflect both, not silently average them away).
**6. Out of scope:** a full Bayesian uncertainty-propagation engine — deliberately not built; this milestone formalizes *representation and honest propagation*, not a new statistical modeling layer, matching the project's consistent preference for the simplest correct mechanism.
**7. Repository impact:** `orchestrator/schemas/uncertainty.py` (new).
**8. New modules:** `orchestrator/schemas/uncertainty.py`, `orchestrator/agents/synthesis/uncertainty_propagation.py`.
**9. Modified modules:** `orchestrator/schemas/agent_io.py` (`Evidence.confidence: float` → `Evidence.uncertainty: UncertaintyEstimate`, additive-compatible via a computed `.confidence` property retained for backward reads), every domain agent, `simulation_engine/models/base.py`, `orchestrator/agents/synthesis/agent.py`.
**10. Public interfaces:**
```python
class UncertaintyEstimate(BaseModel):
    point_estimate: float           # the existing "confidence" number, retained
    lower_bound: float
    upper_bound: float
    source: Literal["data_sparsity", "model_uncertainty", "evidence_conflict", "well_supported"]

def propagate_uncertainty(estimates: list[UncertaintyEstimate]) -> UncertaintyEstimate: ...
```
**11. Internal interfaces:** `propagate_uncertainty` is the one new piece of real logic — a documented, tested combination rule (e.g., interval union widened by conflict penalty when sources disagree, not a naive average), not left to prompt-level LLM judgment the way confidence propagation implicitly has been until now.
**12. Data flow:** `DomainAgent → Evidence(uncertainty=UncertaintyEstimate(...)) → Synthesis aggregates via propagate_uncertainty → SynthesizedClaim carries a real, honestly-combined UncertaintyEstimate, not a re-guessed number`.
**13. Sequence (text):**
```
SeismicAgent -> Evidence: uncertainty=UncertaintyEstimate(0.8, 0.6, 0.9, "well_supported")
OceanAgent -> Evidence: uncertainty=UncertaintyEstimate(0.4, 0.1, 0.6, "data_sparsity")
Synthesis -> propagate_uncertainty: ([seismic_estimate, ocean_estimate])
propagate_uncertainty -> Synthesis: UncertaintyEstimate(0.5, 0.1, 0.75, "evidence_conflict")  [widened, source correctly reflects disagreement]
Synthesis -> SynthesizedClaim: uncertainty=<above>
```
**14. Database impact:** `execution_trace` JSONB now stores structured uncertainty per claim, additive, non-breaking (same policy as Phase 4 M4's citation IDs).
**15. Redis impact:** none.
**16. Background workers:** none new.
**17. LangGraph impact:** none structural — this changes what flows through existing state, not the graph shape.
**18. Evaluation impact:** M1's real ECE calculation now has a genuinely richer signal to evaluate against (bounds, not just a point estimate) — worth revisiting ECE binning strategy once this data exists, noted as future refinement, not required now.
**19. Security impact:** none.
**20. Observability:** log `uncertainty.source` distribution per investigation — a spike in `evidence_conflict` across many investigations would be a genuinely interesting operational signal (the domains are systematically disagreeing about something), worth a future M8 SLO/alert candidate.
**21. Metrics:** `uncertainty_source_distribution`.
**22. Performance:** negligible — this is a data-shape change, not new computation of consequence.
**23. Scalability:** none.
**24. Reliability:** `propagate_uncertainty` must never produce a narrower interval than its inputs individually justify (a correctness property, directly testable) — silently *appearing* more confident after combining conflicting evidence would be a serious, subtle honesty regression.
**25. Error handling:** an agent that doesn't yet emit `UncertaintyEstimate` (a plugin agent built before this milestone lands, relevant once M6 exists) falls back to a `UncertaintyEstimate` synthesized from the legacy `confidence` float with `source="model_uncertainty"` as a conservative default — backward-compatible, not a hard break.
**26. Testing strategy:** unit tests for `propagate_uncertainty`'s combination rule against hand-constructed agreement/disagreement scenarios, specifically testing the "never narrows on conflict" property from point 24 as a named, explicit test. Integration — full Synthesis run with two deliberately-conflicting evidence sources, asserting the final claim's uncertainty correctly reflects `evidence_conflict`.
**27. CI/CD impact:** none new.
**28. Documentation impact:** `docs/phase5/uncertainty_estimation.md` — the combination rule, explained precisely enough that a plugin-agent author (M6) knows exactly what's expected of them.
**29. Migration strategy:** none (JSONB, additive).
**30. Rollback strategy:** the computed backward-compatible `.confidence` property means any consumer that hasn't been updated keeps working during a staged rollout.
**31. Definition of Done:** the "never narrows on conflict" test passes; a real multi-domain investigation with genuinely disagreeing evidence produces a final answer whose stated uncertainty visibly, correctly reflects that disagreement, verified by a human reviewer, not just an automated assertion.
**32. Risks:** none significant — additive schema change with a documented fallback.
**33. Technical debt intentionally accepted:** no full Bayesian propagation (point 6) — named, permanent, by design, not a gap.
**34. Future extensibility:** this is the direct prerequisite for M4 (agents need a shared uncertainty vocabulary to meaningfully negotiate with each other) and M5 (cross-domain claims need honest, combinable uncertainty to be trustworthy).

---

### Milestone 4 — Multi-Agent Collaboration Protocol

**1. Goal:** Give domain agents a bounded, structured way to share findings with each other *during* a single investigation's fan-out — not just report independently to Synthesis afterward — via a new internal `CollaborationMessage` bus.
**2. Engineering motivation:** the current fan-out is embarrassingly parallel by design (Architecture v1.0's own deliberate choice, and correctly so for cost/latency reasons) — but some real reasoning genuinely benefits from one agent's early finding informing another's query. Example: Seismic finding a large event should let Ocean narrow its search window before it even queries NOAA, rather than both querying independently and reconciling only at Synthesis.
**3. Dependencies:** Milestone 3 (agents need a shared `UncertaintyEstimate` vocabulary to make a shared finding meaningfully interpretable by a different agent, not just human-readable to Synthesis).
**4. Architectural rationale:** this is **not** a return to sequential execution — the fan-out remains genuinely parallel; collaboration happens via a small number of bounded, asynchronous "early finding" broadcasts, not synchronous agent-to-agent request/response, which would reintroduce the latency/coupling problems the fan-out design specifically avoided. This is the single most architecturally sensitive milestone in this document, and its scope is deliberately narrow because of that.
**5. Scope:** a `CollaborationBus` (in-memory, per-investigation, torn down at fan-out completion — deliberately not Redis-backed like the SSE event bus, since collaboration messages never need to survive a process restart or cross a worker boundary within a single job execution); each domain agent gets an optional `on_peer_finding(message)` hook it may act on or ignore; a hard cap (e.g., max 2 collaboration rounds) to prevent unbounded cross-talk latency.
**6. Out of scope:** any agent *blocking* on a peer's finding (agents may only *react* to messages that arrive before their own query completes — no agent waits for another) — this is the concrete mechanism that preserves the "genuinely parallel" property; a full negotiation protocol, voting, or consensus mechanism between agents — explicitly not needed for the concrete use case (early-finding narrowing), and would be exactly the premature complexity this document's design philosophy warns against.
**7. Repository impact:** `orchestrator/graph/collaboration_bus.py` (new).
**8. New modules:** `orchestrator/graph/collaboration_bus.py`, `orchestrator/schemas/collaboration.py`.
**9. Modified modules:** `orchestrator/graph/fan_out_coordinator.py` (construct a `CollaborationBus` per fan-out call, pass it to each agent), every domain agent (optional `on_peer_finding` implementation — most will implement a no-op, a small number will genuinely use it).
**10. Public interfaces:**
```python
class CollaborationMessage(BaseModel):
    from_agent: str
    finding_summary: str
    uncertainty: UncertaintyEstimate
    suggested_refinement: dict | None   # e.g. {"region_hint": "narrower bounding box"}

class CollaborationBus:
    async def broadcast(self, message: CollaborationMessage) -> None: ...
    async def peer_findings(self, since_round: int) -> list[CollaborationMessage]: ...
```
**11. Internal interfaces:** `DomainAgent.on_peer_finding(message: CollaborationMessage) -> AgentInput | None` — returning a non-`None` value means "I want to re-run with this refinement," consumed by the coordinator only if the agent hasn't already completed and only within the round cap.
**12. Data flow:**
```
FanOutCoordinator → construct CollaborationBus(investigation_id)
  → launch all agents concurrently, each holding a reference to the bus
  → SeismicAgent completes early, finds a major event → bus.broadcast(CollaborationMessage(...))
  → OceanAgent (still running) → bus.peer_findings() polled at a natural checkpoint in its own execution → on_peer_finding() → returns a refined AgentInput
  → FanOutCoordinator → re-runs OceanAgent once with the refinement (round 1 of max 2) → OceanAgent completes
  → fan-in proceeds exactly as before
```
**13. Sequence (text):**
```
FanOutCoordinator -> CollaborationBus: create(investigation_id)
par
  FanOutCoordinator -> SeismicAgent: run(input, bus)
  SeismicAgent -> USGS: query
  SeismicAgent -> Bus: broadcast(finding)
  SeismicAgent -> FanOutCoordinator: AgentOutput
and
  FanOutCoordinator -> OceanAgent: run(input, bus)
  OceanAgent -> Bus: peer_findings(since_round=0)  [checked once, at a natural point before its own external call]
  Bus -> OceanAgent: [seismic finding]
  OceanAgent -> on_peer_finding: (seismic finding)
  on_peer_finding -> OceanAgent: refined_input
  OceanAgent -> NOAA: query(refined_input)  [only one external call still made — refinement narrows it, doesn't double it]
  OceanAgent -> FanOutCoordinator: AgentOutput
end
FanOutCoordinator -> Synthesis: [proceeds exactly as before]
```
**14. Database impact:** none — the bus is in-memory and ephemeral; the *fact* that collaboration occurred is logged into `execution_trace` (additive) for explainability, but the bus itself persists nothing.
**15. Redis impact:** none — deliberately, per point 5.
**16. Background workers:** none new — this happens entirely within the existing investigation job's execution.
**17. LangGraph impact:** the fan-out node's internal implementation changes (agents now share a bus reference); the graph's node/edge *shape* does not change — collaboration is an implementation detail of the fan-out node, not a new set of graph edges, which is what keeps this from becoming the sequential-execution regression named as out-of-scope.
**18. Evaluation impact:** the benchmark set (M1's real harness) should gain at least one question specifically designed to benefit from collaboration (a scenario where one domain's finding genuinely should narrow another's query) — the concrete way to measure whether this milestone actually improved anything, not just that it runs.
**19. Security impact:** `CollaborationMessage` content flows between agents and could theoretically carry adversarial content if an upstream tool response were compromised — the same prompt-injection defense already required at the Synthesis/Critic boundary (Phase 3) applies here too: any agent consuming a peer's `finding_summary` text must treat it as untrusted data, not instructions, in its own LLM calls if it has any. This must be stated explicitly in `docs/CONTRIBUTING_AGENTS.md` (M6 dependency) so plugin authors don't miss it.
**20. Observability:** log every broadcast and every consumed peer-finding, with `investigation_id`, `from_agent`, `to_agent`, `round` — this is genuinely interesting explainability content, a natural addition to the SSE event catalog (a new `collaboration` event type) though not required for this milestone's own Definition of Done.
**21. Metrics:** `collaboration_rounds_per_investigation`, `collaboration_triggered_rate` (what fraction of investigations actually use this vs. run in pure isolation, expected to be a minority — most queries genuinely don't need it, and that's fine).
**22. Performance:** bounded by the round cap (point 5) — worst-case added latency is one extra bounded round, not unbounded cross-talk.
**23. Scalability:** the bus is per-investigation and torn down immediately after fan-out — zero cross-investigation state, zero contention as investigation volume grows.
**24. Reliability:** a broadcast that no agent is listening for (or that arrives after every other agent has already finished) is a safe no-op, never an error.
**25. Error handling:** `on_peer_finding` raising an exception in one agent must not affect others — wrapped in the same per-agent error boundary already used for the main `run()` call.
**26. Testing strategy:** unit tests for `CollaborationBus`'s round-cap enforcement and no-op-on-no-listener behavior. Integration — a fixture scenario with two agents where one's mocked finding demonstrably changes the other's mocked query parameters, asserting the full refined-input round-trip. Failure-path — `on_peer_finding` exception doesn't crash the fan-out. Concurrency — a broadcast arriving exactly as a peer agent completes (race condition at the boundary) is handled deterministically, not flakily (a specifically important test given this is the one milestone introducing genuine new concurrency surface).
**27. CI/CD impact:** none structurally new.
**28. Documentation impact:** `docs/phase5/multi_agent_collaboration.md`, and the security note from point 19 folded into `docs/CONTRIBUTING_AGENTS.md`.
**29. Migration strategy:** none.
**30. Rollback strategy:** collaboration is additive and optional per-agent (`on_peer_finding` defaults to a no-op) — can be globally disabled via a settings flag with zero effect on the base fan-out behavior, matching the feature-flag discipline established since Phase 3.
**31. Definition of Done:** the race-condition test (point 26) passes deterministically across repeated runs (not just once); the M1-eval-harness collaboration-specific benchmark question (point 18) shows a measurable, real improvement over the pre-collaboration baseline — this milestone's success is proven with real eval data, not just working code, directly modeling the discipline this entire project has been building toward since Phase 4's audit.
**32. Risks:** this is the highest-risk milestone in Phase 5 specifically because it's the first genuinely new concurrency pattern introduced since the original fan-out design — budget real review time here, not just implementation time.
**33. Technical debt intentionally accepted:** no negotiation/voting protocol (point 6) — permanent, by design.
**34. Future extensibility:** M5's cross-domain synthesis upgrade directly builds on agents already being able to reference each other's findings.

**ADR-502: In-Memory, Non-Persistent Collaboration Bus (Not Redis-Backed)**
*Decision:* the `CollaborationBus` is a plain in-process object, scoped to a single fan-out call, never touching Redis.
*Context:* every other cross-component communication mechanism in this project (SSE events, checkpointing) is Redis-backed; it would be consistent-looking to make this one Redis-backed too.
*Alternatives considered:* a Redis pub/sub channel per investigation, mirroring the SSE event mechanism exactly.
*Why in-memory wins:* collaboration messages only ever need to reach agents running in the *same* fan-out call, in the *same* worker process, within a window of seconds — there is no resumability requirement (unlike checkpointing) and no external-consumer requirement (unlike SSE). Adding Redis round-trips to a mechanism explicitly designed to reduce agent-to-agent latency would work directly against this milestone's own goal. Consistency-for-its-own-sake would be the wrong reason to add cost here.
*Future implications:* if agents are ever distributed across multiple worker processes for a single investigation (not currently true, not currently planned), this decision would need revisiting — named explicitly as the condition that would invalidate it, not left implicit.

---

### Milestone 5 — Cross-Domain Evidence Synthesis Upgrade

**1. Goal:** Extend Synthesis's reasoning beyond "merge whatever evidence arrived" into genuine cross-domain pattern recognition — e.g., recognizing that a seismic + ocean-temperature + wildfire pattern together implies something none of the three domains would surface alone.
**2. Engineering motivation:** this is the actual "planetary intelligence" payoff this phase is named for — everything before this milestone (real eval numbers, honest uncertainty, agent collaboration) exists to make this milestone's output trustworthy, not just plausible-sounding.
**3. Dependencies:** Milestone 4 (cross-domain patterns are far more reliably found when agents have already had a chance to share early findings, not just independently-gathered evidence reconciled after the fact).
**4. Architectural rationale:** this is a Synthesis-prompt and Synthesis-logic upgrade, not a new agent and not a new graph node — the existing Synthesis agent already sees all gathered evidence; what's missing is structured guidance and a verification step specifically for cross-domain claims (which are exactly the class of claim most likely to be an LLM pattern-matching artifact rather than a real correlation, and therefore the class of claim the Critic should scrutinize hardest).
**5. Scope:** a new, distinct claim category (`cross_domain_pattern`) alongside the existing single-domain claim shape; Critic verification logic specifically strengthened for this category (requiring, at minimum, that a cross-domain claim cite evidence from 2+ distinct domains, structurally enforced by `CitationMapper`, not just prompted for).
**6. Out of scope:** any new statistical/correlation-detection algorithm — cross-domain pattern recognition remains LLM-reasoning-driven, verified structurally (citation requirements) and empirically (eval benchmark coverage), not by adding a bespoke correlation engine, which would be a significant, unjustified scope expansion for an LLM-orchestration project.
**7. Repository impact:** `orchestrator/schemas/synthesis.py` modified (new `cross_domain_pattern` claim type).
**8. New modules:** none.
**9. Modified modules:** `orchestrator/agents/synthesis/agent.py` (prompt + logic), `orchestrator/agents/synthesis/citation_mapper.py` (the 2+-domain structural requirement for this claim category), `orchestrator/agents/critic/agent.py` (elevated scrutiny for this category specifically).
**10. Public interfaces:**
```python
class SynthesizedClaim(BaseModel):
    # existing fields unchanged
    claim_type: Literal["single_domain", "cross_domain_pattern"] = "single_domain"
```
**11. Internal interfaces:** `CitationMapper.validate_cross_domain(claim) -> bool` — the structural 2+-domain check, a small, focused addition to the existing validator.
**12. Data flow:** unchanged structurally — Synthesis already receives all evidence; this milestone changes what it's asked to look for and how strictly a specific claim category is checked, not the evidence-gathering flow itself.
**13. Sequence (text):**
```
Synthesis -> LLM: [prompt now explicitly asks: "identify any patterns that span 2+ domains, tag them cross_domain_pattern"]
LLM -> Synthesis: claims, some tagged cross_domain_pattern
Synthesis -> CitationMapper: validate(claims)
CitationMapper -> CitationMapper: for cross_domain_pattern claims, additionally check evidence spans 2+ distinct agent_names
alt fails domain-count check
  CitationMapper -> Synthesis: claim rejected [logged: "cross-domain claim cites only 1 domain, downgraded/rejected"]
else passes
  CitationMapper -> Synthesis: claim accepted
end
Synthesis -> Critic: verify(synthesis)  [Critic applies elevated scrutiny specifically to cross_domain_pattern claims]
```
**14. Database impact:** `execution_trace` gains `claim_type` per claim — additive.
**15. Redis impact:** none.
**16. Background workers:** none new.
**17. LangGraph impact:** none structural.
**18. Evaluation impact:** the benchmark set needs at least 2–3 questions specifically designed to have a real, known cross-domain pattern as the correct answer — the concrete way M1's real eval harness measures whether this milestone actually works, not just whether it runs without error.
**19. Security impact:** none beyond what's already covered by Phase 3's prompt-injection framing, which extends unchanged to this new claim category.
**20. Observability:** `cross_domain_claims_per_investigation`, `cross_domain_claim_rejection_rate` (a high rejection rate would indicate the LLM is over-eagerly tagging single-domain claims as cross-domain, a genuinely useful tuning signal).
**21. Metrics:** as above.
**22. Performance:** negligible — same LLM call, richer prompt, no new calls.
**23. Scalability:** none.
**24. Reliability:** the structural 2+-domain requirement means this feature cannot silently degrade into fabricated-sounding cross-domain claims backed by one domain's evidence dressed up in cross-domain language — this is the concrete, load-bearing safety property of this entire milestone.
**25. Error handling:** unchanged from existing Synthesis/CitationMapper patterns.
**26. Testing strategy:** unit — the 2+-domain structural check against a deliberately-single-domain-dressed-as-cross-domain fixture claim, asserting rejection. Integration — a full run against the new eval questions from point 18. Failure-path — a genuinely cross-domain claim with insufficient distinct-domain citations correctly rejected, not silently downgraded to single-domain (an explicit, tested distinction).
**27. CI/CD impact:** none new.
**28. Documentation impact:** `docs/phase5/cross_domain_synthesis.md`.
**29. Migration strategy:** none.
**30. Rollback strategy:** the `claim_type` field defaults to `single_domain`; disabling the new prompt behavior via a settings flag reverts to Phase 4 behavior exactly.
**31. Definition of Done:** the structural-rejection test (point 26) passes; the eval benchmark's cross-domain questions show correct pattern identification at a rate meaningfully above what the pre-Phase-5 system achieved on the same questions (measured, not assumed, per M1's real harness).
**32. Risks:** LLM over-eagerness to find "interesting" cross-domain patterns that aren't real is the central risk this milestone exists to guard against — the structural citation requirement is the primary defense, eval-measured accuracy is the secondary, ongoing check.
**33. Technical debt intentionally accepted:** no bespoke correlation-detection algorithm (point 6), permanent by design.
**34. Future extensibility:** this claim-type pattern (`Literal[...]` extensible enum) is the template for any future specialized claim category Phase 6 might need.

---

### Milestone 6 — Agent Plugin Architecture

**1. Goal:** Evolve Phase 4's static agent-contribution framework (scaffold + CI contract check) into a genuine dynamic-loadable plugin system — a new domain agent can be distributed and installed without a core-team-reviewed merge into `orchestrator/agents/`.
**2. Engineering motivation:** named in Part A.5 as the one deliberate, justified extension of a previously-rejected idea — the static contract has now proven stable across a real contribution framework, which is exactly the precondition that makes dynamic loading safe rather than premature.
**3. Dependencies:** Milestone 1 (a plugin's eval coverage must be checkable against real metrics, not placeholder zeros — a plugin gate that checks against `calculate_calibration() == 0.0` always would be worse than no gate at all).
**4. Architectural rationale:** plugins are Python packages implementing the existing `AgentInput -> AgentOutput` contract plus a new `PluginManifest` (name, version, required settings, declared eval-benchmark-question IDs it should be scored against), discovered via Python entry points (the standard, well-understood mechanism — `importlib.metadata.entry_points`), not a bespoke dynamic-import/sandboxing system built from scratch.
**5. Scope:** the `PluginManifest` schema and loader; a plugin registry that supplements (does not replace) the existing static `orchestrator/agents/registry.py` — core, first-party agents remain exactly as they are, statically registered; only *external* agents go through the plugin path, a deliberate, load-bearing distinction.
**6. Out of scope:** a plugin marketplace/UI, hot-reloading plugins into a running process (plugins are loaded at worker startup only, requiring a restart to add/update one — a deliberately simple, safe boundary, not a limitation this milestone apologizes for), sandboxed/untrusted-code execution (plugins run with the same trust level as first-party code; this is an *extensibility* mechanism for known, reviewed contributors' packages, not a mechanism for running arbitrary untrusted third-party code safely — that would be a fundamentally different, much larger security engineering effort, explicitly not this milestone's job).
**7. Repository impact:** `orchestrator/agents/plugin_loader.py` (new), `orchestrator/schemas/plugin_manifest.py` (new).
**8. New modules:** both above, plus `docs/PLUGIN_DEVELOPMENT.md` (distinct from Phase 4's `CONTRIBUTING_AGENTS.md`, which remains the guide for *first-party* agents added via PR; this new doc is for *plugin* agents distributed independently).
**9. Modified modules:** `orchestrator/agents/registry.py` (gains a `register_plugin(manifest)` path alongside its existing static registration), `workers/worker.py` (plugin discovery at startup).
**10. Public interfaces:**
```python
class PluginManifest(BaseModel):
    name: str
    version: str
    entry_point: str                      # "mypackage.agent:run"
    required_settings: list[str]           # env vars the plugin needs, validated present at load time
    eval_benchmark_question_ids: list[str]  # which benchmark questions this plugin should be scored against

def discover_plugins() -> list[PluginManifest]: ...   # via importlib.metadata.entry_points(group="gaiaos.agents")
def load_plugin(manifest: PluginManifest) -> Callable[[AgentInput], Awaitable[AgentOutput]]: ...
```
**11. Internal interfaces:** `PluginValidationError` raised at startup (not at query time) if a discovered plugin's `entry_point` doesn't conform to the `AgentInput -> AgentOutput` signature (reusing Phase 4's `AgentContractValidator` logic exactly, generalized from a CI-time check to also run as a startup-time check) or if `required_settings` aren't present — a broken plugin must never reach query time, only ever fail loudly at worker boot.
**12. Data flow:** `Worker startup → discover_plugins() → for each: validate contract + settings → register_plugin(manifest) into the same registry the static agents use → Adaptive Planner (Phase 2's classifier) becomes able to route to plugin-provided domains exactly like first-party ones, no special-casing downstream`.
**13. Sequence (text):**
```
Worker -> plugin_loader: discover_plugins()
plugin_loader -> importlib.metadata: entry_points(group="gaiaos.agents")
importlib.metadata -> plugin_loader: [volcanic_activity_plugin's manifest]
plugin_loader -> AgentContractValidator: validate(entry_point signature)
alt valid
  plugin_loader -> registry: register_plugin(manifest)
  Worker -> continue startup
else invalid
  plugin_loader -> Worker: raise PluginValidationError, abort startup  [fail loud, fail early]
end

[at query time, indistinguishable from a first-party agent]
FanOutCoordinator -> registry: get("volcanic_activity")
registry -> FanOutCoordinator: the plugin's loaded callable
```
**14. Database impact:** a small `installed_plugins` table (name, version, installed_at, manifest JSON) for operational visibility (M9's dashboard can show installed plugins) — not required for the loading mechanism itself to function, purely observational.
**15. Redis impact:** none.
**16. Background workers:** plugin discovery happens in every worker process at startup — no new job type, an extension of existing startup behavior.
**17. LangGraph impact:** none structural — a plugin agent is just another node the graph can route to, exactly like a first-party one, by construction.
**18. Evaluation impact:** `eval_benchmark_question_ids` in the manifest is the direct mechanism generalizing Phase 4's `agent_contract_check.yml` "does this agent have eval coverage" check from a CI-time, first-party-only check into something that applies to plugins too — a plugin with zero declared benchmark coverage is loaded with a loud warning, not blocked (plugins aren't necessarily merged into this repo's CI, so a hard block isn't enforceable the way it is for first-party agents — an honest, named limit of this mechanism, not glossed over).
**19. Security impact:** stated plainly in point 6 — plugins run at full trust. `docs/PLUGIN_DEVELOPMENT.md` must say this explicitly and unambiguously, so a plugin author and a deployer both understand a plugin is not a sandbox boundary. This is the single most important thing for this milestone's documentation to get right.
**20. Observability:** `installed_plugins` table (point 14) feeds directly into M9's/Phase 4's admin dashboard as a new panel.
**21. Metrics:** per-plugin success rate, latency — tagged distinctly from first-party agent metrics so a misbehaving plugin is immediately identifiable, not blended into aggregate domain-agent metrics.
**22. Performance:** plugin discovery adds a small, one-time startup cost — negligible relative to existing worker boot time.
**23. Scalability:** plugins scale exactly like first-party agents (same fan-out mechanism, same timeout/partial-results policy from Phase 2) — no new scaling dimension introduced.
**24. Reliability:** a plugin agent that times out or errors is handled by the exact same partial-results/timeout machinery already governing first-party agents — no special-casing, no new failure mode.
**25. Error handling:** `PluginValidationError` at startup (point 11) is the primary new error surface — must produce a message naming the specific plugin and the specific validation failure, mirroring Phase 4's `agent_contract_check.yml` error-message discipline.
**26. Testing strategy:** unit — manifest validation against a deliberately-malformed fixture plugin (wrong signature, missing required setting). Integration — a real, minimal test plugin package built as a fixture, installed into the test environment, discovered and successfully routed to end-to-end. Failure-path — a plugin failing validation correctly aborts worker startup rather than silently skipping the broken plugin (a deliberate, tested fail-loud choice, not fail-open, since a silently-skipped plugin is a worse operational surprise than a worker that won't start).
**27. CI/CD impact:** a new, minimal "plugin compatibility" CI job that installs the fixture test plugin against the current `AgentInput`/`AgentOutput`/`UncertaintyEstimate` schemas — catches a first-party schema change that would silently break the external plugin contract, which is exactly the kind of cross-boundary regression this project's existing drift-check philosophy (OpenAPI, requirements, agent contract) would predict is worth guarding structurally rather than trusting to memory.
**28. Documentation impact:** `docs/PLUGIN_DEVELOPMENT.md` (new, primary deliverable), explicit cross-link from `docs/CONTRIBUTING_AGENTS.md` clarifying the distinction between "contribute a first-party agent via PR" and "distribute your own plugin independently."
**29. Migration strategy:** `installed_plugins` table via standard Alembic migration.
**30. Rollback strategy:** plugin discovery is entirely additive and can be disabled via a settings flag (`PLUGINS_ENABLED=false`) with zero effect on first-party agent behavior.
**31. Definition of Done:** the fixture test plugin (point 26) is discovered, validated, and successfully routed to in an integration test; a deliberately-broken fixture plugin correctly aborts worker startup with a specific, actionable error message.
**32. Risks:** the full-trust security model (point 19) is the one thing this milestone must not let anyone misunderstand — worth a deliberate, explicit warning banner at the top of `docs/PLUGIN_DEVELOPMENT.md`, not just a line buried in a security-considerations section.
**33. Technical debt intentionally accepted:** no sandboxing, no hot-reload, no marketplace (point 6) — all permanent, by design, not gaps to close later without a new, separately-justified reason.
**34. Future extensibility:** if untrusted third-party plugin execution ever becomes a real product requirement, this milestone's manifest/discovery mechanism is the foundation a sandboxing layer would sit on top of — not wasted work even in that hypothetical future, but explicitly not this milestone's scope.

**ADR-503: Python Entry Points Over a Bespoke Plugin Protocol**
*Decision:* plugin discovery uses `importlib.metadata.entry_points`, the standard Python packaging mechanism.
*Context:* a bespoke discovery mechanism (e.g., a `plugins/` directory scanned at startup, or a config file listing plugin module paths) was the other realistic option.
*Alternatives considered:* directory-scanning (simpler to explain, but requires plugins to be physically present in a specific filesystem location relative to the app, awkward for independently-`pip install`-distributed plugins) and a config-file allowlist (explicit and auditable, but adds an extra manual step for every install that entry points handle automatically via normal `pip install`).
*Why entry points win:* it's the same mechanism the Python packaging ecosystem already uses for exactly this purpose (pytest plugins, Flask extensions, etc.) — a plugin author already familiar with the Python ecosystem needs zero GaiaOS-specific plugin-discovery knowledge, only the `AgentInput`/`AgentOutput`/`PluginManifest` contract itself. This directly serves the "contributor friendliness" design principle by minimizing bespoke surface area a newcomer has to learn.
*Future implications:* ties plugin distribution to PyPI/pip conventions — acceptable and expected for a Python-native project; would need revisiting only if GaiaOS ever needed to support non-Python plugins, which is not a stated goal anywhere in this project's history.

---

### Milestone 7 — Horizontal Scalability: Workers & Read Path

**1. Goal:** Convert Phase 4's advisory worker-scaling recommendation into a real, tested horizontal-scaling deployment story (multiple worker replicas, verified safe under concurrent execution), and add a Postgres read-replica path for the metrics/eval read-heavy queries that don't need write-consistency.
**2. Engineering motivation:** Phase 4 deliberately built the *signal* (queue depth, recommended pool size) without the *actuation*; this milestone checks whether real operational data (now available after a full phase of production use) justifies building the actuation, per Phase 4's own named trigger condition.
**3. Dependencies:** none hard-blocking, but this milestone's first concrete action is literally "look at the `recommended_pool_size` data Phase 4 has been collecting" — if that data doesn't show a real, recurring need, this milestone's scope shrinks to "document that it's still not needed yet," which is itself a legitimate, honest outcome (see point 31).
**4. Architectural rationale:** horizontal worker scaling only works safely if concurrent workers don't corrupt shared state — this milestone's real engineering content is *verifying* that property (RQ's own job-locking semantics, the checkpointer's per-investigation isolation via `thread_id`) under genuine concurrent load, not building new infrastructure from scratch.
**5. Scope:** a load test proving N concurrent workers process a burst of investigations correctly (no double-processing, no lost jobs, no checkpoint collision); Postgres read-replica configuration for `metrics/aggregation.py` and `eval/harness` queries specifically (the two genuinely read-heavy, latency-tolerant paths); `docker-compose.yml` updated to support a `worker` replica count as a first-class, documented parameter.
**6. Out of scope:** Kubernetes, any autoscaling actuator, write-path read replicas (investigation status polling still reads from the primary, since staleness there is a real, visible user-facing correctness issue in a way it isn't for a 7-day metrics rollup).
**7. Repository impact:** `db/session.py` gains an optional read-replica engine (used only by the two named read-heavy call sites, not globally), `docker-compose.yml` modified.
**8. New modules:** `tests/load/test_concurrent_worker_processing.py` (a genuinely new test category for this project — the first load test).
**9. Modified modules:** `db/session.py`, `metrics/aggregation.py`, `eval/harness/runner.py`, `docker-compose.yml`, `config/settings.py` (`READ_REPLICA_DATABASE_URL`, optional — absent means read queries fall back to the primary, a safe default for anyone not yet running a replica).
**10. Public interfaces:**
```python
def get_read_session() -> AsyncSession: ...   # routes to replica if configured, primary otherwise
```
**11. Internal interfaces:** none beyond the above.
**12. Data flow:** `metrics/aggregation.aggregate_metrics() → get_read_session() → replica if configured, else primary, transparently`.
**13. Sequence (text):**
```
Admin -> API: GET /api/v1/admin/metrics
API -> metrics/aggregation: aggregate_metrics(...)
aggregate_metrics -> get_read_session: ()
alt READ_REPLICA_DATABASE_URL configured
  get_read_session -> Replica: SELECT ...
else
  get_read_session -> Primary: SELECT ...
end
```
**14. Database impact:** requires a configured Postgres streaming replica at the infrastructure level (deployment concern, not a schema migration — this milestone's code is replica-aware, not responsible for standing the replica up, which is an operations/infra task documented in `ops/runbooks/`, not application code).
**15. Redis impact:** none.
**16. Background workers:** the load test (point 8) specifically exercises N worker replicas processing a concurrent burst.
**17. LangGraph impact:** none — this milestone verifies existing checkpoint isolation holds under real concurrency, it doesn't change graph behavior.
**18. Evaluation impact:** none directly.
**19. Security impact:** a read-replica connection string is a second database credential — must be scoped to read-only at the Postgres role level (a `GRANT SELECT`-only role), not just "pointed at a replica and trusted to only ever run reads" — stated explicitly as a hard requirement, not a suggestion.
**20. Observability:** replica lag becomes a new thing worth monitoring (a stale replica serving metrics queries could show misleadingly out-of-date numbers) — `replica_lag_seconds` metric, a candidate for a future M8 SLO/alert if replicas are actually deployed.
**21. Metrics:** as above.
**22. Performance:** the direct point of the read-replica half of this milestone — offloading read-heavy aggregation queries from the primary, which matters more as investigation-write volume grows.
**23. Scalability:** the direct point of the worker-replica half.
**24. Reliability:** the load test (point 8) is this milestone's core reliability deliverable — proving, not assuming, that horizontal scaling is safe.
**25. Error handling:** replica connection failure → transparent fallback to primary (never fail a metrics request just because the optional replica is unreachable) — a specific, tested behavior.
**26. Testing strategy:** the concurrent-worker load test (point 8) is the centerpiece — N simulated workers, a burst of M investigations, asserting exactly M completions, zero duplicates, zero lost jobs, zero checkpoint cross-contamination between investigations. Unit — replica-fallback logic. Integration — real replica-configured test environment (if feasible in CI; if not, explicitly documented as a manual pre-release verification step, an honest disclosed limitation rather than a hidden gap).
**27. CI/CD impact:** the load test likely runs as a separate, longer-running, possibly-manually-triggered CI job (mirroring Phase 4's nightly-eval pattern) rather than blocking every PR — same reasoning as that prior decision, restated here.
**28. Documentation impact:** `ops/runbooks/horizontal_scaling.md` (new) — how to actually stand up additional worker replicas and a read replica in a real deployment, since this milestone's code readiness is only half the story.
**29. Migration strategy:** none application-side; replica setup is an infrastructure/ops task.
**30. Rollback strategy:** `READ_REPLICA_DATABASE_URL` unset reverts to Phase 4 behavior exactly; worker replica count is just a deployment parameter, trivially reduced back to 1.
**31. Definition of Done:** the concurrent-worker load test passes cleanly at a meaningful scale (e.g., 4 workers, 100 concurrent investigations); **or**, if Phase 4's own `recommended_pool_size` data genuinely shows no real need yet, this milestone's Definition of Done becomes a written, evidence-backed statement to that effect, and the load-test/replica code ships as verified-but-currently-unused capability rather than being built and immediately load-bearing — both are legitimate, honest outcomes, and which one applies is itself a finding this milestone is responsible for producing, not assuming in advance.
**32. Risks:** if the load test reveals a real checkpoint-isolation bug under concurrency, that's a Critical finding against Phase 3's own durable-execution design — flagged here as a real possibility this milestone must be prepared to surface honestly, not softened.
**33. Technical debt intentionally accepted:** no Kubernetes, no autoscaling actuator — named, permanent until the documented trigger (Part A.4) actually fires.
**34. Future extensibility:** if the load test and real operational data together do justify an autoscaling actuator later, Phase 4's `recommended_pool_size` pure function is already the decision logic it would call.

---

### Milestone 8 — Operational Excellence: SLOs & Error Budgets

**1. Goal:** Formalize explicit Service Level Objectives — both operational (latency, availability) and, novel for this project, *reasoning-quality* (calibration, citation-fallback rate) — and rewire Phase 4's alerting rules to be SLO-derived rather than ad hoc thresholds.
**2. Engineering motivation:** Phase 4 built alerting; it did not build a principled reason for *which* thresholds matter or *how much* budget is acceptable to spend before it's a real problem — this is the standard SRE maturity step, applied here for the first time, and applied to reasoning quality (not just uptime), which is the genuinely novel part for a project like this.
**3. Dependencies:** Milestone 1 (quality SLOs need real calibration/precision numbers to be defined against) and Milestone 7 (capacity SLOs are more meaningful once real scaling behavior is understood, not guessed at).
**4. Architectural rationale:** this is a policy and configuration layer on top of Phase 4's existing `alerting/` package — `AlertRule` gains an explicit `slo_target` and `error_budget_window`, and the evaluator's firing logic changes from "threshold crossed → fire" to "error budget consumption rate → fire before the budget is exhausted, not just after a single breach," the standard, well-understood SRE error-budget-burn-rate pattern.
**5. Scope:** SLO definitions for: p95 investigation latency (operational), job success rate (operational), calibration ECE (quality), citation-fallback rate (quality, from Phase 4 M4). Error-budget-burn-rate alerting logic added to `alerting/evaluator.py`.
**6. Out of scope:** a full SLO-management UI (Phase 4's dashboard gains a new panel showing current budget consumption, but a dedicated SLO-editing interface is not built — SLOs are defined in versioned config, reviewed via normal PR process, which is the right level of ceremony for decisions this consequential).
**7. Repository impact:** `alerting/slo.py` (new).
**8. New modules:** `alerting/slo.py`, `config/slo_definitions.yaml` (versioned, human-readable, PR-reviewable — deliberately not a database table, since SLO changes are rare, high-consequence decisions that benefit from git history and code review, not a runtime-editable admin form).
**9. Modified modules:** `alerting/rules.py`, `alerting/evaluator.py`.
**10. Public interfaces:**
```python
class SLODefinition(BaseModel):
    name: str
    target: float                # e.g. 0.99 for 99% success rate
    window: str                  # e.g. "30d"
    error_budget_burn_alert_threshold: float   # e.g. alert if burning budget 10x faster than sustainable

def evaluate_slo_burn_rate(slo: SLODefinition, actuals: list[float]) -> BurnRateResult: ...
```
**11. Internal interfaces:** `BurnRateResult(current_burn_rate, budget_remaining_pct, alert_severity)`.
**12. Data flow:** `alert_evaluation_job (Phase 4 M3's existing scheduled job) → for each SLODefinition: pull recent actuals from metrics/aggregation (operational) or eval_benchmark_runs (quality) → evaluate_slo_burn_rate → fire/resolve exactly as Phase 4's incident lifecycle already does, now SLO-labeled`.
**13. Sequence (text):**
```
Scheduler -> alert_evaluation_job: run()  [unchanged trigger, Phase 4 M3]
alert_evaluation_job -> config/slo_definitions.yaml: load SLODefinitions
loop for each SLO
  alert_evaluation_job -> metrics/aggregation OR eval_benchmark_runs: pull actuals
  alert_evaluation_job -> evaluate_slo_burn_rate: (slo, actuals)
  alt burn rate exceeds threshold
    alert_evaluation_job -> AlertIncident: create [Phase 4 M3's existing table, now slo_name-tagged]
    alert_evaluation_job -> notifier: notify
  end
end
```
**14. Database impact:** `alert_incidents` (Phase 4 M3) gains an `slo_name` column — additive.
**15. Redis impact:** none.
**16. Background workers:** reuses Phase 4 M3's existing scheduled evaluation job — no new job type.
**17. LangGraph impact:** none.
**18. Evaluation impact:** the quality SLOs (calibration, citation-fallback) are the direct, load-bearing consumer of M1's real numbers — this is where "the eval harness produces real data" (M1) becomes "the eval harness's real data drives real operational decisions" (this milestone), closing the loop the Phase 4 audit specifically flagged as broken.
**19. Security impact:** none.
**20. Observability:** budget-consumption-over-time becomes a first-class dashboard panel (Phase 4 M9 extended) — the most valuable new visualization this milestone produces.
**21. Metrics:** `slo_burn_rate` per SLO, `slo_budget_remaining_pct` per SLO.
**22. Performance:** negligible — runs on the existing scheduled cadence.
**23. Scalability:** none.
**24. Reliability:** burn-rate alerting (vs. simple threshold alerting) is itself a reliability improvement — it fires *before* a budget is fully exhausted, giving operators lead time, which simple threshold-crossing alerting structurally cannot do.
**25. Error handling:** missing actuals data (e.g., a new SLO defined before enough history exists) → explicit "insufficient data" state, never a false-positive or false-negative alert from an empty window.
**26. Testing strategy:** unit — burn-rate math against known synthetic time series (a well-defined, testable statistical calculation, same rigor as M1's ECE tests). Integration — a full evaluation cycle against seeded metrics/eval data, asserting correct SLO-labeled incident creation. Edge case — the "insufficient data" state from point 25, explicitly tested, not just hoped for.
**27. CI/CD impact:** none structurally new.
**28. Documentation impact:** `docs/phase5/slos.md` — every SLO's definition and, critically, *why that specific target* was chosen (99%? 95%? — a real, defensible number, not an arbitrary one), mirroring the "explain why, not just what" documentation discipline this project has maintained since Phase 1.
**29. Migration strategy:** standard Alembic migration for the `slo_name` column.
**30. Rollback strategy:** `config/slo_definitions.yaml` can be emptied to disable all SLO-based alerting with zero code change, falling back to Phase 4's original threshold-based rules if they're still separately configured.
**31. Definition of Done:** the burn-rate unit tests pass against known-correct synthetic scenarios; a deliberately-seeded budget-exhaustion scenario correctly fires an alert *before* full exhaustion (proving the "lead time" property is real, not just claimed).
**32. Risks:** SLO target-setting is a genuine judgment call (point 28) — ship with conservative, clearly-reasoned initial targets, explicitly revisited after enough real production data accumulates, not treated as permanent on first guess.
**33. Technical debt intentionally accepted:** no SLO-editing UI (point 6) — permanent, by design, config-as-code is the deliberate choice here.
**34. Future extensibility:** the `SLODefinition`/burn-rate pattern generalizes to any future metric worth an SLO (e.g., cross-domain-claim accuracy from M5, once enough eval history exists to define a target against it responsibly).

---

### Milestone 9 — Public Research API & Dataset Publishing

**1. Goal:** A read-only, SLO-backed, versioned public API (`/api/v1/research/*`) exposing aggregated, anonymized investigation findings and the causal-chain hazard dataset, plus a periodic published dataset export — GaiaOS's intelligence output made genuinely available beyond its own operators for the first time.
**2. Engineering motivation:** Part A.5's second deliberate extension — a "planetary intelligence system" whose intelligence only its own team can see is a materially smaller claim than this project's own stated mission.
**3. Dependencies:** Milestone 6 (plugin-contributed domains may be worth publishing, and the plugin registry's `installed_plugins` visibility is relevant to what a research consumer should know is powering a given finding) and Milestone 8 (a public-facing API without SLO backing is a promise this project isn't yet positioned to keep responsibly — sequenced last specifically so it's the capstone, not a rushed afterthought).
**4. Architectural rationale:** this is purely a new, additive read surface on top of existing data (`investigations`, `hazard_events`, `hazard_relationships`) — no new write path, no new reasoning capability, which keeps this milestone's risk profile appropriately bounded for something facing the public internet for the first time.
**5. Scope:** `GET /api/v1/research/investigations` (aggregated, anonymized — no `user_id`, no raw query text unless the submitting user explicitly opted in, a new `consent_public_research` flag on `investigations`), `GET /api/v1/research/hazard-events` (already-public-source data — USGS/NOAA are public data to begin with, so this is genuinely low-risk), a scheduled monthly dataset export job (reusing the M3/M6/M8-established scheduler pattern for the fourth time) publishing a versioned, checksummed archive to public object storage.
**6. Out of scope:** any write access, any per-consumer API key issuance beyond what Phase 3's existing API-key mechanism already provides (reused, not rebuilt), a public-facing UI for browsing the dataset (the API and the export are the deliverable; a browsing experience is legitimate future work, explicitly not this milestone's).
**7. Repository impact:** `app/api/v1/research.py` (new).
**8. New modules:** `app/api/v1/research.py`, `workers/jobs/dataset_export_job.py`.
**9. Modified modules:** `db/models/investigation.py` (`consent_public_research: bool = False` — opt-in, never opt-out-by-default, a deliberate, non-negotiable privacy stance), `app/api/v1/investigations.py` (the consent flag settable at submission time).
**10. Public interfaces:**
```
GET /api/v1/research/investigations?domain=seismic&since=2026-01-01
  -> paginated, anonymized: {query_category, domains_involved, complexity_tier, confidence_summary, created_at}
  [never raw query text unless consent_public_research=true on that specific investigation]

GET /api/v1/research/hazard-events?event_type=earthquake&region=...
  -> the existing hazard_events data, already-public-source, no anonymization needed
```
**11. Internal interfaces:** `AnonymizationPolicy` — a single, explicit, tested module defining exactly what fields are stripped/generalized for non-consented investigations, so "what counts as anonymized" is one reviewable piece of code, not scattered logic across multiple endpoints.
**12. Data flow:**
```
External researcher -> API: GET /api/v1/research/investigations
API -> RateLimiter: scope="research_api" [Phase 4 M2's pattern, a new scope, same mechanism]
API -> AnonymizationPolicy: apply(investigations, respecting consent_public_research per row)
API -> Researcher: paginated, anonymized response

Scheduler (monthly) -> dataset_export_job: run()
dataset_export_job -> Postgres: SELECT consenting investigations + all hazard_events
dataset_export_job -> AnonymizationPolicy: apply
dataset_export_job -> Object Storage: publish versioned, checksummed archive
dataset_export_job -> metrics: emit(DatasetExportCompleted)
```
**13. Sequence (text):** covered above; the export job reuses Phase 4 M6's backup-job structural pattern almost exactly (scheduled, checksummed, shipped to object storage), the fourth reuse of that idiom in this project's history.
**14. Database impact:** `investigations.consent_public_research` column, additive.
**15. Redis impact:** the new `research_api` rate-limit scope, reusing Phase 4 M2's existing mechanism.
**16. Background workers:** `dataset_export_job`, the fourth scheduled-job type (ingestion, alerting, backup, now this).
**17. LangGraph impact:** none.
**18. Evaluation impact:** none directly, though a published, versioned dataset is itself a valuable external validation mechanism over time (outside researchers can independently assess data quality) — a genuine, if indirect, long-term evaluation asset.
**19. Security impact:** this is the highest-consequence privacy decision in this project's history — `AnonymizationPolicy` must be the single, most rigorously tested module in this milestone (point 11), and `consent_public_research` defaulting to `False` (point 9) is the specific, non-negotiable design decision that makes this milestone safe to ship at all. Rate limiting on the research API must be tuned independently from the authenticated-user API (Phase 4 M2's `scope` mechanism already supports this) since this surface is, by design, reachable by anonymous or lightly-authenticated external consumers.
**20. Observability:** `research_api_requests`, `dataset_export_size_trend`, `consenting_investigation_rate` (what fraction of users opt in — a genuinely interesting product signal).
**21. Metrics:** as above.
**22. Performance:** research API queries are read-heavy and latency-tolerant — routes through Milestone 7's read replica if configured, another direct, planned reuse of a prior milestone's work.
**23. Scalability:** rate-limited and read-replica-backed by construction — bounded exposure from day one.
**24. Reliability:** covered by Milestone 8's SLO framework — this is the first surface this project has built with an explicit external-facing availability promise, and it inherits the SLO/alerting infrastructure specifically built to make that promise responsibly, rather than being the reason that infrastructure gets rushed.
**25. Error handling:** standard `ErrorResponse` pattern, unchanged from every other API surface in this project.
**26. Testing strategy:** `AnonymizationPolicy` gets the most rigorous test suite in this milestone — every field, tested for both the consenting and non-consenting path, with an explicit test asserting no PII-adjacent field (raw query text, user_id, IP-derived data) ever appears in a non-consenting row's response, checked exhaustively against the full response schema, not spot-checked. Integration — full research-API request/response cycle. Load — the research API specifically, given its new, different (anonymous/external) traffic pattern from the rest of the system.
**27. CI/CD impact:** the anonymization test suite (point 26) should be a required, named CI gate — a regression here is a privacy incident, not a bug, and deserves the same "this must never silently pass" treatment this project has given its most consequential correctness properties elsewhere (citation fabrication, in Phase 2/4).
**28. Documentation impact:** a public-facing `docs/research-api/` (distinct from internal `docs/phase5/`, since this is the first documentation genuinely written for an external, non-contributor audience), an explicit, plain-language data-use/privacy statement.
**29. Migration strategy:** standard Alembic migration for `consent_public_research`.
**30. Rollback strategy:** the entire research API surface can be disabled via a settings flag with zero effect on the rest of the system — the consistent, by-now-well-established feature-flag discipline applied to the highest-stakes milestone in this document.
**31. Definition of Done:** the anonymization exhaustive-field test (point 26) passes with zero PII-adjacent leakage across every tested field; a real monthly export runs successfully and is independently verifiable (checksum matches, archive is genuinely parseable by a fresh, unaffiliated script); the research API meets its M8-defined SLO under a realistic load test.
**32. Risks:** this is the second-highest-risk milestone in this document, after M4, for an entirely different reason — M4's risk is concurrency correctness, this milestone's risk is privacy correctness, and getting it wrong has reputational and possibly legal consequences a code bug alone wouldn't. Budget real review time proportional to that risk, not to the (actually fairly small) amount of new code involved.
**33. Technical debt intentionally accepted:** no public browsing UI (point 6) — legitimate future work, not a gap in this milestone's own scope.
**34. Future extensibility:** this is explicitly the foundation Phase 6 would build a public-facing product experience on top of, if that's ever a stated goal — not assumed here, just noted as the natural next step this milestone makes possible.

**ADR-504: Opt-In Consent, Never Opt-Out, for Public Research Data**
*Decision:* `investigations.consent_public_research` defaults to `False`; only explicitly-consenting investigations' raw content is ever eligible for anonymized publication (aggregated, category-level statistics may still include non-consenting rows in a way that reveals nothing investigation-specific, e.g., "N investigations touched the seismic domain this month" — a genuinely aggregate count, not a de-anonymizable statistic about any one investigation).
*Context:* the alternative — publish everything by default, let users opt out — is common in industry but was rejected outright, not seriously weighed as a close call.
*Alternatives considered:* opt-out-by-default (rejected: most users never change defaults, meaning "opt-out" in practice means "publish nearly everything," which is a much larger privacy commitment than this project should make on users' behalf without their affirmative choice). A fully separate "research mode" submission flow (rejected as unnecessary complexity — a single boolean flag on the existing submission endpoint achieves the same outcome with far less new surface area).
*Why opt-in wins:* it is the only choice consistent with this project's demonstrated pattern of choosing the more conservative, more honest option whenever privacy/trust and convenience are in tension (the same instinct that produced the non-enumeration password-reset design in Phase 4 M2, and the explicit-gap-over-fabrication principle throughout).
*Future implications:* the consenting-investigation rate (point 20) becomes a real signal for whether this feature is actually gathering enough data to be a useful public resource — if it's very low, that's valuable, honest information about whether this feature is achieving its goal, not a reason to quietly loosen the default later without a new, explicit decision.

---

## Part D — After All Milestones

### D.1 Overall Phase 5 Architecture
Two tracks converge at Milestone 9. The **Reasoning Quality track** (M1 → M3 → M4 → M5 → M6) is where this phase's actual mission — better, more honest, more collaborative intelligence — lives. The **Platform Maturity track** (M2, M7 → M8) is where the operational rigor to responsibly expose that intelligence externally gets built. M9 is only possible, and only responsible, because both tracks land first.

### D.2 System Dependency Graph
```
Reasoning Quality:                    Platform Maturity:
M1 (Real Calibration/Precision)        M2 (Repo/Supply-chain hygiene) [independent]
  │
M3 (Uncertainty Estimation)            M7 (Horizontal Scalability) [independent]
  │                                       │
M4 (Multi-Agent Collaboration)         M8 (SLOs) [depends on M1, M7]
  │                                       │
M5 (Cross-Domain Synthesis)              │
  │                                       │
M6 (Plugin Architecture) [depends M1]    │
  │                                       │
  └───────────────┬───────────────────────┘
                   │
             M9 (Public Research API) [depends M6, M8]
```

### D.3 Milestone Dependency Graph (explicit)
M1 → M3 → M4 → M5; M1 → M6; M7 → M8; M1 → M8; M6 + M8 → M9. M2 depends on nothing and blocks nothing.

### D.4 Critical Implementation Order
Single engineer: **M1 → M2 → M3 → M4 → M5 → M7 → M8 → M6 → M9.** (M6 is deliberately placed after M8 rather than immediately after M1 in this linearization — while M6 only *architecturally* depends on M1, it's the highest-effort, highest-judgment milestone in the Reasoning Quality track, and sequencing the Platform Maturity track's more mechanical work first gives a single engineer a natural momentum-building order without violating any real dependency.)
Two engineers: one takes M1 → M3 → M4 → M5 → M6, the other takes M2 → M7 → M8 in parallel, converging at M9.

### D.5 Parallelizable Milestones
M2 is fully parallel to everything. M7 is fully parallel to the entire Reasoning Quality track. M3/M4/M5/M6 are strictly sequential within their own track (each genuinely needs the one before it, per Part C's stated dependencies — this was checked specifically for false sequential constraints and none were found; every dependency in the Reasoning Quality track is real).

### D.6 Risks If Milestones Are Implemented Out of Order
- **M4 before M3:** agents would collaborate using bare confidence floats with no shared honesty vocabulary — exactly the inconsistency M3 exists to close, reintroduced at the one point (agent-to-agent trust) where it matters most.
- **M6 before M1:** a plugin eval-gate checking against permanently-zero calibration/precision numbers is actively worse than no gate — it would give plugin authors false confidence their agent passed quality review.
- **M9 before M8:** a public-facing API with no SLO backing is a promise this project can't respmore than gesture at, undermining exactly the trust this milestone exists to build.
- **M9 before M6:** the research API's documentation would have no honest way to describe what's powering a plugin-contributed domain's findings, since plugins wouldn't exist yet to describe.

### D.7 Future Technical Debt (Named, Not Hidden)
- No sandboxed/untrusted plugin execution (M6) — real, permanent, until a concrete need for genuinely untrusted third-party code execution materializes.
- No Bayesian uncertainty propagation (M3) — real, permanent, by design.
- No Kubernetes/autoscaling actuator (M7) — conditionally permanent, pending the load test's actual findings.
- No SLO-editing UI (M8) — permanent, by design.
- No public dataset-browsing UI (M9) — real future work, not a gap in this phase's own scope.

### D.8 Phase 6 Prerequisites
- Real production traffic data from M9's public API is the concrete input Phase 6 needs before deciding whether a public-facing product experience (beyond API + dataset export) is justified.
- M7's load-test findings determine whether Phase 6 needs to revisit the "no autoscaling actuator" decision.
- The consenting-investigation rate (M9) is the key signal for whether the research-data flywheel is real enough to invest further in.

### D.9 Updated Engineering Roadmap
Phase 1: foundation. Phase 2: reasoning core. Phase 3: trust infrastructure. Phase 4: operational maturity and open-source readiness. Phase 5: reasoning honesty, collaboration, and responsible external exposure. The through-line holds across all five: build the smallest correct thing the current, real requirement justifies; verify with real tests and real numbers, never assumed ones (Phase 5's entire first milestone exists because that discipline slipped exactly once, three phases ago, and this document's first job is closing that gap before building anything new on top of it); defer everything else with a named, honest trigger condition.

### D.10 Production Maturity Assessment (Post-Phase 5)
GaiaOS exits Phase 5 as a system whose reasoning quality is genuinely measured (not assumed), whose agents genuinely collaborate within honest, bounded limits, whose extensibility story is real and safe within clearly-stated trust boundaries, and whose most consequential public commitment (the research API) is backed by real SLOs rather than good intentions. This is the point at which "production-grade planetary intelligence system," the phrase this phase opened with, becomes a claim this document can defend with evidence rather than aspiration.

---

## Part E — Verification, Exit Criteria, and Checklists

### E.1 Per-Milestone Verification Summary
Every milestone's own Part C entry already specifies its unit/integration/failure-path tests, CI additions, and Definition of Done. Two milestones carry additional, named test categories beyond the standard set: **M4 requires a concurrency/race-condition test** (Part C, M4.26) and **M7 requires a genuine load test** (Part C, M7.8/26) — both first-of-their-kind for this project, both flagged as requiring proportionally more review attention than their line-count would suggest.

### E.2 Phase 5 Exit Criteria
- M1's ECE/precision fix verified against real statistical fixtures, not just "runs without error."
- M4's race-condition test passes deterministically across repeated runs.
- M5's cross-domain benchmark questions show measured improvement over the pre-Phase-5 baseline.
- M6's fixture plugin is discovered, validated, and successfully routed to end-to-end; its failure-path (broken plugin aborts startup) is proven, not assumed.
- M7's load test either passes at a meaningful scale or produces an honest, evidence-backed "not yet needed" finding.
- M8's burn-rate alerting fires with real lead time before budget exhaustion in a seeded test scenario.
- M9's anonymization test suite shows zero PII-adjacent leakage across an exhaustive field check, and a real monthly export completes and is independently verifiable.

### E.3 Engineering Audit Checklist for Phase 5 Completion
1. Re-verify every Part 1-style prior-finding table entry — confirm nothing regressed, exactly as every prior phase's closing audit has done.
2. Independently recompute ECE against the raw eval data, not just trust M1's own reported number.
3. Independently attempt to trigger the M4 race condition under deliberately adversarial timing.
4. Independently install a second, adversarially-malformed fixture plugin (not the one M6 shipped its own test with) and confirm it's rejected.
5. Independently run the M7 load test a second time, on different hardware/environment, confirming the result isn't an artifact of one specific test run.
6. Independently review `AnonymizationPolicy` (M9) field-by-field against the full `Investigation` schema, not just the fields the milestone's own tests happened to check.

### E.4 Production Readiness Checklist
All of Phase 4's E.3 criteria (incident detection without human noticing first, dashboard-based diagnosis, a genuinely-executed restore drill, contributor self-sufficiency, self-verifying documentation) **plus**: reasoning-quality regressions are detected by real metrics, not silent placeholders (M1); the system's most externally-visible commitment (M9) is SLO-backed with proven burn-rate alerting (M8).

### E.5 Operational Readiness Checklist
Worker horizontal scaling is either proven safe under load or honestly documented as not-yet-needed (M7); a read replica, if deployed, has its lag actively monitored (M7); every scheduled job type (ingestion, alerting, backup, dataset export) shares one well-understood, well-tested scheduling mechanism, not four different ones (verified true by construction across M3-of-Phase-4 through M9-of-Phase-5).

### E.6 Open Source Maturity Checklist
A genuine, safe plugin path exists for external contributors who don't want to go through the core-team PR process for every new domain (M6), with an unambiguous, prominently-stated trust-boundary disclosure; the project's intelligence output is now something an external researcher can point to and evaluate independently (M9), which is a genuinely different and stronger open-source signal than "the code is open" alone.
