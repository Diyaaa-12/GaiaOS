# GaiaOS — Phase 7 Complete Roadmap & Planning Document

**Role:** Principal Software Architect
**Baseline:** Phases 1–6 complete, frozen at v0.6.4, audited independently six times across this engagement. Nothing below redesigns them.
**Mission continuity:** Phase 6 made GaiaOS's data real. Phase 7 makes its intelligence *legible* (explainability, research value), its ecosystem *reachable* (SDK, CLI), and its scale *earned, not assumed* (horizontal maturity before distributed metrics before Kubernetes — in that order, and only as far as real evidence justifies).

This document consolidates all four Phase 7 planning deliverables — the roadmap, the implementation order, the milestone dependency graph, and the milestone summary — into a single reference, with additional detail (effort estimates, a consolidated verification quick-reference, and expanded cross-references between sections) not present in any one of the original four files individually.

---

## Table of Contents

- **Part I — Repository Review** (state of the platform entering Phase 7)
- **Part II — The Seven Milestones** (full detail: purpose, architecture, dependencies, implementation order, verification, documentation, testing, acceptance criteria — plus effort estimates)
- **Part III — What Was Deliberately Not Added**
- **Part IV — Implementation Order** (single-engineer critical path, two-engineer parallelization, conditional-outcome milestones)
- **Part V — Milestone Dependency Graph** (text diagram, dependency table, cross-track independence analysis)
- **Part VI — Milestone Summary** (at-a-glance table, one-line summaries, design rationale)
- **Part VII — Consolidated Verification Quick-Reference** (new — every milestone's acceptance bar in one table)

---

# Part I — Repository Review

*(Full detail assumed known from six prior independent engineering audits performed across this engagement; summarized here as the baseline this roadmap builds from.)*

- **Reasoning Core:** LangGraph orchestration, six domain agents, Adaptive Planner (heuristic), Synthesis/Critic with structural citation validation, bounded Critic replan loop (feature-flagged), Multi-Agent Collaboration Bus (Phase 5 M4), Cross-Domain Synthesis (Phase 5 M5), Agent Plugin Architecture (Phase 5 M6).
- **Evidence & Retrieval:** Hybrid pgvector + BM25 retrieval, real arXiv-sourced literature corpus (Phase 6 M4), PostGIS geometry + OSM administrative boundaries (Phase 6 M3) for causal reasoning.
- **Evaluation & Quality:** Real ECE/retrieval-precision metrics (Phase 5 M1), 18+ benchmark questions, nightly CI regression gate, SLO/error-budget alerting (Phase 5 M8).
- **Platform Services:** JWT + API key auth, RBAC, Redis rate limiting, durable RQ workers with checkpoint-based resume, advisory worker-scaling policy (Phase 5 M7), resilience layer with per-source circuit breakers and degraded-mode (Phase 6 M1).
- **Data & Ingestion:** USGS, NOAA, OpenAQ, FIRMS, Open-Meteo, Copernicus/Sentinel, ERA5, GDELT — all resilience-wrapped, scheduled, cursor-deduplicated. Simulation models calibrated against real historical outcomes (Phase 6 M5).
- **Extensibility:** Agent plugin loader (entry-points based), MinIO-optional backup/dataset storage, public research API (Phase 5 M9).
- **Known, honestly-carried debt:** documentation-currency drift (recurring, structural fix still not built), `_extract_location`'s hardcoded fallback (unmeasured, not yet acted on), Phase 5 M5/M9's promotion-gate and anonymization tests (open verification items, not confirmed regressed).

**What Phase 7 does not need to build:** anything already covered above. Every milestone in Part II was checked against this list specifically to avoid duplicating existing capability.

---

# Part II — The Seven Milestones

## Milestone 1 — Explainability & Reasoning Trace Exploration

**Purpose:** GaiaOS has stored a rich `execution_trace` (nodes executed, evidence, citations, critic flags, collaboration events, uncertainty sources) since Phase 2, and has streamed it live via SSE since Phase 2's Milestone 9 — but there has never been a way to *explore* a completed investigation's reasoning after the fact beyond reading raw JSON. This milestone builds that exploration surface, extending the admin dashboard (Phase 4 M9) with an investigation-detail view: a real, navigable graph of what the system did and why, not just what it concluded.

**Architecture:** Read-only consumer of existing data — no new write path, no new reasoning capability, mirroring the deliberately-bounded-risk pattern Phase 5 M9 established for its own first public-facing surface. `admin_ui/` gains an `InvestigationTrace` view rendering the existing `execution_trace` JSONB as an interactive node graph (reusing the same event taxonomy the SSE stream already defines — `agent_started`, `evidence_found`, `synthesizing`, `critic_flag`, `replanning`, `collaboration` — as the graph's node types, so there is exactly one event vocabulary in this system, not two). A new, additive `GET /api/v1/investigations/{id}/trace` endpoint serves the structured trace in a frontend-friendly shape (the raw JSONB reorganized into a node/edge list), rather than requiring the frontend to parse the storage format directly — keeping the storage schema free to evolve without breaking the UI contract.

**Dependencies:** None blocking — pure read layer over existing Phase 2–6 data. Sequenced first because it's the lowest-risk, highest-immediate-value milestone (no new external dependency, no new data source, no new write path) and because Milestone 2's pattern-mining view reuses this milestone's graph-rendering components rather than building its own.

**Implementation order:**
1. `GET /trace` endpoint + trace-shape transformation logic, tested against real historical `execution_trace` data spanning every phase's contributions (collaboration events only exist post-Phase-5, replan events only exist when the feature flag was on — the transformer must handle traces from before those features existed gracefully, not assume every trace has every event type).
2. `admin_ui` `InvestigationTrace` view.
3. Cross-link from the existing investigation-list view.

**Verification strategy:** Render a real Phase 6-era investigation (with collaboration, cross-domain claims, and a degraded-mode evidence gap all present in the same trace) and confirm every event type is legible in the UI, not just present in the JSON. Render a pre-Phase-5 historical investigation (no collaboration events) and confirm the UI degrades gracefully rather than erroring on missing fields.

**Documentation updates:** `docs/phase7/explainability.md`; a short addition to `docs/CONTRIBUTING_AGENTS.md` noting that any new event type a future agent or plugin introduces should be added to the shared taxonomy this milestone formalizes, not invented ad hoc.

**Testing requirements:** Unit tests for the trace-shape transformer across every historical event-type combination named above. Frontend component tests for the graph view against fixture trace data. Integration test: real investigation submitted, completed, trace fetched and rendered end-to-end.

**Acceptance criteria:** A human reviewer can look at the rendered trace for a real multi-domain, collaboration-involving investigation and correctly explain, without reading raw logs, why the system reached its conclusion and what it was uncertain about — the concrete, human-verifiable bar for "explainability," not just "the endpoint returns 200."

**Estimated difficulty:** Medium (the transformation logic's cross-phase-compatibility requirement is the genuinely tricky part; the UI itself is a standard graph-rendering exercise).
**Estimated time:** 2–3 sessions for the endpoint + transformer, 2–3 sessions for the `admin_ui` view, 1 session for integration/polish — roughly 5–7 sessions total.

---

## Milestone 2 — Longitudinal Pattern Mining & Research Insights

**Purpose:** Every investigation to date has been reasoned about in isolation. With real, growing historical data (Phase 6 M2's expanded sources), a real literature corpus (Phase 6 M4), and calibrated simulation models (Phase 6 M5), GaiaOS now has enough real substrate to ask a genuinely new class of question: not "what happened here," but "what patterns recur across many investigations and many real historical events over time." This is the most direct "research value" capability this platform has ever had the data to support honestly.

**Architecture:** A new, scheduled (not query-time) analysis job — `workers/jobs/pattern_mining_job.py` — reusing the now-five-times-proven scheduler pattern, which periodically analyzes the `hazard_events`/`hazard_relationships` tables (now populated by six real sources) for statistically-notable recurring co-occurrence patterns (e.g., "seismic activity in region X is followed by ocean-temperature anomalies within N days at a rate meaningfully above baseline"), distinct from any single investigation's Causal Chain agent query. Results are stored in a new `pattern_findings` table (each finding: description, supporting event IDs, statistical confidence, `UncertaintyEstimate` per Phase 5 M3's shared vocabulary — this is not a new confidence concept, it's the existing one applied to a new subject) and surfaced via an additive `GET /api/v1/research/patterns` endpoint (Phase 5 M9's research API namespace, extended, not duplicated) and a corresponding `admin_ui` panel reusing Milestone 1's graph-rendering components for pattern visualization.

**Dependencies:** Milestone 1 (reuses its visualization components); Phase 6 M2/M5 (needs real, multi-source historical data and calibrated models to produce findings worth trusting — mining patterns from the old two-source, uncalibrated data would have produced far less defensible results, which is the concrete reason this milestone waited for Phase 6 rather than landing earlier).

**Implementation order:**
1. Statistical co-occurrence detection logic (a well-defined, testable calculation — correlation/co-occurrence rate above a documented baseline threshold, not a vague "look for patterns" LLM prompt; this is deliberately *not* LLM-driven, since a statistical claim about historical data should be statistically computed and then, optionally, LLM-summarized for readability — never LLM-guessed).
2. `pattern_findings` schema + scheduled job.
3. Research API extension.
4. `admin_ui` panel.

**Verification strategy:** Seed a fixture dataset with a deliberately-planted, known co-occurrence pattern and a deliberately-planted absence of one, asserting the mining job finds the real one and correctly does not fabricate the absent one — the same "structural, not vibes-based" correctness discipline this project has applied to citation validation since Phase 2, applied here to a new subject.

**Documentation updates:** `docs/phase7/pattern_mining.md` — the statistical methodology, in enough detail for a domain scientist to assess it, matching the documentation bar Phase 6 M5's calibration methodology set.

**Testing requirements:** Unit tests for the co-occurrence statistic itself against known-correct synthetic data. Integration test for the full scheduled job against the fixture dataset above. A regression test ensuring `pattern_findings` never overwrites/loses a prior finding silently (findings should be versioned/timestamped, not clobbered on each run, since "did this pattern strengthen or weaken over time" is itself valuable information).

**Acceptance criteria:** The planted-pattern fixture test passes; a real run against real Phase 6 ingested data produces at least one finding a domain-knowledgeable reviewer judges plausible and well-supported, not just statistically present.

**Estimated difficulty:** Medium-High (the statistical methodology needs real care — false-positive pattern detection is the central risk this milestone must guard against, mirroring Phase 5 M5's "LLM over-eagerness" risk but for a statistical rather than LLM-driven mechanism).
**Estimated time:** 3–4 sessions for the detection logic and its fixture-based correctness tests, 2 sessions for the schema/job/API, 2 sessions for the dashboard panel — roughly 7–8 sessions total.

---

## Milestone 3 — Python SDK
*(Backlog item — deferred from Phase 6, now placed.)*

**Purpose:** GaiaOS's API has been versioned and stable since Phase 3 M10, and has had one real external-shaped consumer (Phase 5 M9's research API, Phase 6's own `admin_ui` treating the backend as an external client) proving the contract holds. A typed Python client library is the concrete, low-risk next step toward real ecosystem adoption — notebooks, automation scripts, and third-party integrations all become dramatically easier with `pip install gaiaos-sdk` instead of hand-rolled `httpx` calls against raw OpenAPI.

**Why now, not earlier:** the backlog's own deferral reasoning was exactly right — an SDK against an API that was still gaining new endpoints every phase (auth in Phase 3, alerting/backups in Phase 4, research/collaboration in Phase 5, nothing new to the core investigation API in Phase 6) would have meant repeated breaking SDK releases. Six phases in, `/api/v1`'s core surface (`investigations`, `auth`, `api-keys`) has been stable since Phase 4, and this milestone's own Milestone 1/2 additions are the last planned additions before the SDK locks onto a genuinely mature contract.

**Architecture:** A separate, independently-versioned, independently-releasable package (`sdk/python/`, published to PyPI) — **generated from the existing published OpenAPI spec (Phase 4 M10) wherever the generator's output is good enough, hand-written only where it isn't** (streaming/SSE consumption in particular needs a hand-written, ergonomic wrapper; CRUD-shaped endpoints are good generation candidates). This mirrors the exact "generate, don't hand-maintain, to prevent drift" discipline this project has applied to the OpenAPI spec itself and to `requirements.lock` — applied a third time, to a new artifact, rather than inventing a fourth documentation-currency risk this project has already learned (repeatedly, per every prior audit) is expensive to leave manual.

**Dependencies:** None architecturally, but sequenced after Milestones 1–2 specifically so the SDK's first release covers the complete, current API surface rather than needing an immediate follow-up release once those land.

**Implementation order:**
1. OpenAPI-to-SDK generation pipeline (evaluate `openapi-python-client` or equivalent — a build-time tool decision, not a runtime dependency, so it doesn't affect GaiaOS's own free-first deployment footprint at all).
2. Hand-written SSE streaming wrapper (`client.investigations.stream(id)` as an async generator — the one part of the API a generic OpenAPI generator handles poorly).
3. A CI step verifying the generated SDK is current against the live spec (the same drift-check idiom, applied a fourth time, this time to an artifact worth publishing externally, which raises the stakes of staleness rather than lowering them).

**Verification strategy:** A real notebook-style integration test — submit an investigation, stream progress, retrieve the final trace (Milestone 1's endpoint) — all through the SDK only, no raw `httpx` calls, proving the SDK is genuinely sufficient for real usage, not just technically complete.

**Documentation updates:** `sdk/python/README.md` with a genuine, runnable quickstart; a link from the main `README.md` and `docs/api/` — the SDK's own documentation-currency risk mitigated by the generation pipeline in point 3, not by manual diligence alone.

**Testing requirements:** Unit tests for the hand-written streaming wrapper. Integration test (point above) against a real running GaiaOS instance in CI. The drift-check CI step itself.

**Acceptance criteria:** `pip install gaiaos-sdk` (from a test PyPI index in CI, real PyPI at release) followed by the notebook-style integration flow succeeds with zero raw HTTP code required from the consumer.

**Estimated difficulty:** Low-Medium (the generation pipeline is well-trodden ground; the SSE wrapper is the one genuinely custom piece).
**Estimated time:** 2 sessions for the generation pipeline setup, 2 sessions for the SSE wrapper, 1–2 sessions for the drift-check CI and documentation — roughly 5–6 sessions total.

---

## Milestone 4 — CLI Wizard
*(Backlog item — deferred from Phase 6, now placed.)*

**Purpose:** A `gaiaos` command-line tool for the operations a contributor or operator currently has to do by hand: submit an investigation and watch it stream, manage API keys, and — directly reusing Phase 5 M6's existing `scripts/scaffold_new_agent.py` — scaffold a new plugin agent, now as a proper installable CLI subcommand rather than a standalone script a contributor has to know exists.

**Architecture:** Built directly on Milestone 3's SDK (`gaiaos = "gaiaos_cli.main:app"` as a `pip`-installable console-script entry point, using `typer` or equivalent for a genuinely pleasant CLI experience) — this is deliberately *not* a separate HTTP client implementation; the CLI is the SDK's first and primary real consumer, which is both good dogfooding and the concrete reason Milestone 3 had to come first.

**Dependencies:** Milestone 3 (hard dependency — the CLI has no reason to duplicate HTTP logic the SDK already provides).

**Implementation order:**
1. `gaiaos auth login` / `gaiaos investigate "<query>" --stream` (the core, most-used flows).
2. `gaiaos plugin scaffold <name>` (wraps Phase 5 M6's existing scaffold logic — a genuine UX improvement over "know to find and run a script buried in `scripts/`", not new logic).
3. `gaiaos admin` subcommands (API-key management, gated the same way the underlying API already gates them — the CLI adds no new authorization logic, it only calls existing, already-secured endpoints).

**Verification strategy:** A first-time-contributor persona test (mirroring the DX-persona review method this engagement's audits have used repeatedly) — someone unfamiliar with GaiaOS's HTTP API completes `gaiaos investigate` and `gaiaos plugin scaffold` using only `--help` output and the CLI's own quickstart, no other documentation.

**Documentation updates:** `docs/cli/README.md`; the CLI becomes the primary onboarding path referenced from the main `README.md`'s quickstart, replacing (not duplicating) the current raw-`curl`-based quickstart example.

**Testing requirements:** Unit tests per subcommand (mocked SDK calls). Integration test for the full `investigate --stream` flow against a real instance. The plugin-scaffold subcommand's output must pass Phase 5 M6's existing `agent_contract_check.yml` unmodified — a direct, testable proof this milestone didn't quietly diverge from that established contract.

**Acceptance criteria:** The first-time-contributor persona test passes; the scaffolded-plugin CI check (above) passes without modification to the existing Phase 5 workflow.

**Estimated difficulty:** Low (thin wrapper over an already-built SDK and already-built scaffold script; the value here is UX polish, not new engineering complexity).
**Estimated time:** 1–2 sessions per subcommand group (auth/investigate, plugin scaffold, admin) — roughly 4–5 sessions total.

---

## Milestone 5 — Horizontal Scaling Maturity

**Purpose:** Phase 5 M7 deliberately built the *signal* (advisory `recommended_pool_size`) without the *actuation*, explicitly pending real operational evidence. Two phases of real production-shaped usage later (Phase 6's six new ingestion sources, Milestone 1–2's new scheduled jobs), this is the natural point to look at that evidence honestly and, if it justifies it, build genuine multi-node worker deployment guidance and tooling — still not autoscaling infrastructure, still not Kubernetes, but a real, tested, documented path to running more than one worker node reliably.

**Architecture:** This milestone's *first, real deliverable* is an honest look at Phase 5 M7's collected `recommended_pool_size`/queue-depth data (mirroring that milestone's own Definition of Done, which explicitly allowed "not yet needed" as a legitimate outcome). If the data justifies it: multi-node worker deployment documentation and a genuine load test at real multi-node scale (extending Phase 5 M7's single-node concurrent-worker test, which already found and fixed real event-loop-lifecycle bugs — this milestone's job is confirming those same fixes hold across physically separate nodes, not just separate processes on one host, which is a genuinely different and non-trivial thing to verify). If the data does *not* justify it: this milestone's deliverable becomes a written, evidence-backed statement to that effect, and Milestone 6 is explicitly re-evaluated (see Milestone 6's own dependency note) rather than built on a false premise.

**Dependencies:** None blocking, but sequenced after the Intelligence/Ecosystem tracks specifically because this project's own consistent discipline (Architecture v1.0 onward) is to let real usage justify scaling investment, not to build it speculatively — Milestones 1–4 give the system two more milestones' worth of real usage to accumulate before this one asks "is more scale actually needed yet."

**Implementation order:**
1. Data review against Phase 5 M7's own named trigger condition.
2. If justified: multi-node Docker Compose deployment reference (documented, not a new orchestrator — still Compose, just documented for a multi-VPS topology, consistent with "extend Docker Compose, don't replace it" until Milestone 7's explicitly-optional territory).
3. Multi-node load test.

**Verification strategy:** The multi-node load test (if built) must specifically re-verify Phase 5 M7's event-loop-lifecycle fixes hold under genuine network-separated concurrency, not just re-run the existing single-node test on more hardware.

**Documentation updates:** `ops/runbooks/multi_node_deployment.md` (if justified) or a documented, dated "evaluated, not yet needed" note in `docs/phase7/` (if not) — both are legitimate, both are required outputs of this milestone either way.

**Testing requirements:** The multi-node load test, if built, following the same rigor as Phase 5 M7's original (exact completion counts, zero duplicates, zero lost jobs, zero checkpoint cross-contamination — now across nodes, not just processes).

**Acceptance criteria:** A clear, evidence-backed answer — not an assumption either way — to "does GaiaOS need multi-node worker deployment yet," with the corresponding deliverable (runbook+load-test, or honest deferral note) produced regardless of which answer the evidence supports.

**Estimated difficulty:** Low for the evidence review itself; Medium-High if the multi-node load test is actually built (genuine distributed-systems testing, real infrastructure needed for CI or a documented manual verification step).
**Estimated time:** 1 session for the evidence review and written outcome. If proceeding: 2–3 sessions for deployment documentation, 3–4 sessions for the multi-node load test — roughly 1 session (deferred outcome) to 7–8 sessions (built outcome).

---

## Milestone 6 — Distributed Metrics Aggregation
*(Backlog item — deferred from Phase 6, now placed, with its own stated dependency honored explicitly.)*

**Purpose:** The backlog's own deferral reasoning was precise: "should only be introduced when Phase 7 includes horizontal scaling capabilities." **This milestone's dependency on Milestone 5 is therefore not just sequencing — it's conditional scope.** If Milestone 5's honest evidence review concludes multi-node deployment isn't yet justified, this milestone's scope shrinks correspondingly: single-node in-memory/Redis-backed metrics (Phase 4 M9, Phase 5 M8) remain entirely correct and sufficient, and building distributed aggregation on top of them would be exactly the "adding complexity without enough value" this roadmap's own instructions ask to reject. **This document explicitly does not force this milestone to build something if Milestone 5 doesn't justify it** — stated here, not left implicit, per the roadmap brief's own instruction to explain such calls plainly.

**Architecture (if Milestone 5 justifies it):** Metrics collection remains per-node (each worker/app instance still emits its own events, unchanged); aggregation moves from a single Postgres `metrics` table queried directly (Phase 4 M9's current design) to a proper time-series-aware aggregation layer — the concrete, well-scoped addition being **Prometheus** (free, self-hosted, the standard, boring, correct choice for exactly this problem) scraping each node, with Phase 4's existing `metrics/aggregation.py` API surface *reimplemented* to query Prometheus instead of Postgres directly, **not exposed as a second, parallel metrics API** — `admin_ui` and the alerting evaluator (Phase 4 M3/Phase 5 M8) continue calling the same internal interface, now backed differently, a clean swap behind an already-existing abstraction boundary, not a new one invented for this milestone.

**Dependencies:** Milestone 5, conditionally, exactly as described above.

**Implementation order (if justified):**
1. Prometheus added as an optional Compose service (off by default for single-node deployments, exactly matching Milestone 5's own "extend, don't replace, Compose" discipline and Phase 6 M6's MinIO opt-in precedent).
2. `metrics/aggregation.py`'s internal implementation swapped to query Prometheus, external interface unchanged.
3. Alerting (Phase 5 M8) and the admin dashboard (Phase 4 M9) re-verified against the new backend, proving the abstraction boundary held.

**Verification strategy:** The existing SLO burn-rate alert tests (Phase 5 M8) and admin dashboard metrics tests (Phase 4 M9) must pass **unmodified** against the new backend — the concrete, testable proof this was a clean swap, not a parallel system.

**Documentation updates:** `docs/phase7/distributed_metrics.md`, explicitly stating the conditional nature of this milestone and, if deferred, the honest note explaining why, cross-linked from Milestone 5's own documentation.

**Testing requirements:** As in "verification strategy" — reused, not new, test suites passing against a swapped backend is the actual bar.

**Acceptance criteria:** Either (a) Prometheus-backed aggregation passes every existing alerting/dashboard test unmodified, or (b) a documented, evidence-backed statement that this milestone is correctly out of scope for this phase, exactly mirroring Milestone 5's own two-valid-outcomes design.

**Estimated difficulty:** Medium (Prometheus integration itself is well-trodden; the discipline of keeping the swap genuinely transparent to every existing consumer is the real engineering care required).
**Estimated time (if built):** 1–2 sessions for the optional Compose service, 3–4 sessions for the aggregation-layer swap, 2 sessions for re-verifying existing test suites pass unmodified — roughly 6–8 sessions. **If deferred: under 1 session** (the written rationale alone).

---

## Milestone 7 — Kubernetes / Helm Deployment Path (Explicitly Optional, Non-Default)
*(Backlog item — deferred from Phase 6, placed last and most conditionally of all four backlog items.)*

**Purpose:** An optional, clearly-labeled enterprise deployment path for organizations that already run Kubernetes infrastructure and want GaiaOS to fit into it — **never a replacement for, or an implied upgrade from, Docker Compose**, which remains and will remain this project's primary, default, student-first deployment target.

**Why this is placed last, and why it's the one milestone in this document most likely to be correctly deferred further:** Helm charts for a system with no real multi-node deployment story (Milestone 5) and no real distributed metrics (Milestone 6) would be charts for infrastructure this project doesn't yet have evidence anyone needs — the single clearest case in this entire roadmap of "adding complexity without enough value" if built ahead of its own prerequisites. **This document's explicit recommendation: build Milestone 7 within Phase 7 only if Milestone 5's evidence review genuinely justifies multi-node deployment; otherwise, defer Milestone 7 to Phase 8 in its entirety, re-evaluated at that point against then-current evidence, rather than building a Kubernetes path for a workload that has never demonstrated needing one.** This is not a soft "nice to have" — it is this document's considered engineering judgment, stated plainly per the roadmap brief's own instruction to reject or move weak milestones rather than preserve them by default.

**Architecture (if built):** Helm charts are a packaging of the *existing* container images (`app`, `worker`, `scheduler`, `admin_ui` — all four already built and CI-verified since Phase 4/5) into Kubernetes manifests — no new application code, no new business logic, a deployment-tooling addition only. Postgres/Redis/MinIO remain either self-hosted-in-cluster (via standard, well-known community Helm charts, not reinvented) or externally managed, at the deployer's choice — GaiaOS's own chart does not mandate either.

**Dependencies:** Milestone 5 (conditionally, per above) and, if Milestone 6 was built, Milestone 6 (since a multi-node K8s deployment without distributed metrics would be flying blind operationally).

**Implementation order (if built):**
1. Helm chart authoring against the existing, unchanged container images.
2. A documented, tested `helm install` path on a real (e.g., k3s, for a genuinely free/self-hostable K8s target — not assuming a paid managed Kubernetes service, consistent with free-first even in this "enterprise path" milestone) test cluster in CI.
3. Explicit, prominent documentation stating Docker Compose remains the recommended default.

**Verification strategy:** A real `helm install` against a real (k3s-in-CI) cluster, followed by the same investigation-submit-and-stream smoke test Milestone 1-of-Phase-1's Docker Compose CI verification originally established — proving the K8s path delivers the same correctness the Compose path already guarantees, not a lesser or different experience.

**Documentation updates:** `docs/deployment/kubernetes.md`, explicitly subordinate to and cross-linked from the primary, Compose-based deployment documentation — never presented as the "more serious" or "more production-grade" option, since Compose-on-a-VPS is and remains a completely legitimate production deployment for this project's actual stated audience.

**Testing requirements:** The `helm install` + smoke-test CI job (point above), run on the same cadence as other infrequent, longer-running CI jobs this project already has precedent for (Phase 4/5's nightly-eval, Phase 5 M7's load test) — not on every PR.

**Acceptance criteria:** The k3s smoke test passes; or, if Milestone 5's evidence doesn't justify proceeding, this milestone is formally deferred to Phase 8 with a written rationale, which is itself a complete and acceptable Phase 7 outcome for this specific milestone.

**Estimated difficulty:** Medium (Helm charting itself is standard, well-documented practice; the k3s-in-CI smoke test is the more novel piece for this project specifically).
**Estimated time (if built):** 2–3 sessions for chart authoring, 2–3 sessions for the CI smoke-test pipeline, 1 session for documentation — roughly 5–7 sessions. **If deferred: under 1 session** (the written rationale alone).

---

# Part III — What Was Deliberately Not Added

Per this roadmap's explicit instruction to reject weak ideas rather than preserve them:

- **No new domain agents** — nothing in the current usage evidence justifies one, and the Agent Plugin Architecture (Phase 5 M6) is the correct, already-built path for anyone who does want one, including this project's own team if evidence ever justifies it.
- **No multi-tenant organizational data model** — excluded, consistently, for the sixth consecutive phase, still correctly, absent a new reason.
- **No real-time/online model retraining** — Phase 6 M5's ADR-603 reasoning against it still holds, unchanged.
- **No dedicated mobile app or non-admin end-user UI** — no evidence of end-user demand distinct from the research API's own consumers, who are already well-served by Milestone 3's SDK.

---

# Part IV — Implementation Order

## Single-Engineer Critical Path

```
M1 (Explainability & Trace Exploration)
  → M2 (Longitudinal Pattern Mining)
    → M3 (Python SDK)
      → M4 (CLI Wizard)
        → M5 (Horizontal Scaling Maturity — evidence review)
          → M6 (Distributed Metrics — conditional on M5)
            → M7 (Kubernetes/Helm — conditional on M5, and on M6 if M6 was built)
```

**Rationale for this exact order:**

1. **M1 before M2** — M2 reuses M1's graph-rendering components; building M2's visualization from scratch first would mean throwing work away once M1 lands.
2. **M2 before M3** — the SDK should cover the complete, current API surface (including M1/M2's new endpoints) in its first release rather than needing an immediate breaking follow-up.
3. **M3 before M4** — hard dependency; the CLI is built on the SDK, not a second HTTP client.
4. **M4 before M5** — no dependency relationship, but M4 is low-risk, high-onboarding-value, and finishes the Ecosystem track cleanly before the Scale track begins, which is the track most likely to produce a "not yet needed" outcome and shouldn't be started prematurely just to fill sequence.
5. **M5 before M6** — hard, explicit dependency per the backlog's own stated reasoning: distributed metrics are only justified once horizontal scaling is real, not advisory.
6. **M6 before M7** — M7 needs M6's operational visibility (if M6 was built) to be deployable responsibly at the multi-node scale K8s implies; if M6 wasn't built (because M5's evidence didn't justify it), M7 is deferred to Phase 8 in its entirety, not attempted on a smaller, unjustified footing.

## Two-Engineer Parallelization

**Engineer A (Intelligence/Ecosystem track):** M1 → M2 → M3 → M4
**Engineer B (Scale track, starts once M1/M2 have landed enough real usage data to inform M5's evidence review — not from day one):** M5 → M6 → M7

The two tracks do not share code dependencies (verified: M1–M4 touch `admin_ui/`, `sdk/`, `docs/cli/`; M5–M7 touch `workers/`, `ops/`, deployment manifests — no file-level overlap), so parallelization is safe from a merge-conflict standpoint. The only reason Engineer B doesn't start on Day 1 is that M5's evidence review is more meaningful with two more milestones' worth of real usage behind it — a scheduling preference, not a hard blocker; a team with an urgent, independent reason to start the Scale track immediately could do so without violating any real dependency.

## Milestones With Legitimate "Do Not Build" Outcomes

Two milestones in this roadmap have an explicitly acceptable outcome of *not building the originally-scoped deliverable*:

- **M5** may conclude "multi-node deployment not yet justified" — a complete, valid Definition of Done, not a failure.
- **M6** is *conditionally scoped on M5's outcome* — if M5 concludes "not yet justified," M6 does not proceed to building Prometheus-backed aggregation at all this phase.
- **M7** is conditionally scoped on both M5 and M6 — if either concludes "not yet needed" for their respective reasons, M7 defers to Phase 8 as a complete milestone in its own right.

This is a deliberate design property of this roadmap, not an oversight: it prevents the Scale track from building infrastructure ahead of evidence, consistent with this project's engineering philosophy across all six prior phases.

---

# Part V — Milestone Dependency Graph

## Graph (text form)

```
                          ┌─────────────────────────────┐
                          │  M1 — Explainability &        │
                          │  Trace Exploration            │
                          │  (no dependencies — root)     │
                          └───────────────┬───────────────┘
                                          │  reuses graph-rendering components
                                          ▼
                          ┌─────────────────────────────┐
                          │  M2 — Longitudinal Pattern     │
                          │  Mining & Research Insights    │
                          │  (depends on M1; also depends  │
                          │   on Phase 6 M2/M5's real data)│
                          └───────────────┬───────────────┘
                                          │  API surface must be final before SDK cut
                                          ▼
                          ┌─────────────────────────────┐
                          │  M3 — Python SDK                │
                          │  (no hard dependency; sequenced │
                          │   after M1/M2 to avoid an        │
                          │   immediate breaking release)   │
                          └───────────────┬───────────────┘
                                          │  hard dependency — CLI built on SDK
                                          ▼
                          ┌─────────────────────────────┐
                          │  M4 — CLI Wizard                │
                          │  (depends on M3)                │
                          └─────────────────────────────┘

                          ┌─────────────────────────────┐
                          │  M5 — Horizontal Scaling         │
                          │  Maturity                        │
                          │  (no hard dependency; depends on │
                          │   Phase 5 M7's collected evidence)│
                          └───────────────┬───────────────┘
                                          │  CONDITIONAL — only if M5 justifies scale
                                          ▼
                          ┌─────────────────────────────┐
                          │  M6 — Distributed Metrics         │
                          │  Aggregation                      │
                          │  (depends on M5's outcome,        │
                          │   explicitly, per backlog)        │
                          └───────────────┬───────────────┘
                                          │  CONDITIONAL — only if M5 (and M6, if built) justify it
                                          ▼
                          ┌─────────────────────────────┐
                          │  M7 — Kubernetes / Helm            │
                          │  Deployment Path (optional)        │
                          │  (depends on M5, and on M6 if built)│
                          └─────────────────────────────┘
```

## Dependency Table

| Milestone | Hard Dependencies | Conditional Dependencies | Can Run in Parallel With |
|---|---|---|---|
| M1 | None | — | M5 (different subsystems, though sequenced later by preference) |
| M2 | M1 | Benefits from Phase 6 M2/M5 real data (already satisfied) | M5 |
| M3 | None | Sequenced after M1/M2 to avoid a breaking follow-up release | M5, M6 (if M5 proceeds) |
| M4 | M3 | — | M5, M6, M7 |
| M5 | None | Its own outcome gates M6 and M7 | M1, M2, M3, M4 |
| M6 | — | **M5 must conclude scale is justified** | M4 (if M3 done) |
| M7 | — | **M5 must conclude scale is justified; if M6 was built, M7 depends on it too** | Nothing — last in its track |

## Cross-Track Independence

The Intelligence/Ecosystem track (M1–M4) and the Scale track (M5–M7) share no file-level or module-level dependencies:

- M1–M4 touch: `admin_ui/`, `app/api/v1/investigations.py` (additive endpoint), `app/api/v1/research.py` (additive endpoint), `sdk/`, `docs/cli/`.
- M5–M7 touch: `workers/`, `ops/`, `metrics/aggregation.py` (internal implementation only, per M6's explicit "swap behind the existing interface" design), deployment manifests.

This independence is a deliberate architectural property, verified during roadmap design, not an accident — it is what makes the two-engineer parallelization in Part IV safe.

---

# Part VI — Milestone Summary

| # | Milestone | Track | Backlog Item? | Depends On | Risk | Outcome Type |
|---|---|---|---|---|---|---|
| M1 | Explainability & Reasoning Trace Exploration | Intelligence | No | None | Low | Always builds |
| M2 | Longitudinal Pattern Mining & Research Insights | Intelligence | No | M1 | Medium | Always builds |
| M3 | Python SDK | Ecosystem | **Yes** | None (sequenced after M1/M2) | Low | Always builds |
| M4 | CLI Wizard | Ecosystem | **Yes** | M3 (hard) | Low | Always builds |
| M5 | Horizontal Scaling Maturity | Scale | No | None | Medium | **Conditional — evidence-gated outcome** |
| M6 | Distributed Metrics Aggregation | Scale | **Yes** | M5 (conditional) | Medium | **Conditional — may not build this phase** |
| M7 | Kubernetes / Helm Deployment Path | Scale | **Yes** | M5, M6 (conditional) | Low (if built) | **Conditional — may defer to Phase 8** |

## One-Line Summary Per Milestone

- **M1:** Turn the execution trace this project has stored since Phase 2 into something a human can actually explore, not just log-read.
- **M2:** Use six phases of now-real data to find patterns across investigations, not just within one.
- **M3:** A real, generated-not-hand-maintained Python client, timed to land once the API surface is genuinely stable.
- **M4:** A CLI built on the SDK, not a second HTTP client — the SDK's first real consumer.
- **M5:** Honestly check whether Phase 5's advisory scaling signal now justifies real multi-node deployment — and accept "not yet" as a complete, valid answer if that's what the evidence says.
- **M6:** Build distributed metrics only if M5 says horizontal scale is real — exactly matching the backlog's own stated reasoning, not built by default.
- **M7:** An explicitly optional, never-default Kubernetes path — likely the single milestone in this roadmap most likely to be correctly deferred to Phase 8 in full.

## What Makes This Roadmap Different From a Naive "Add the Four Backlog Items" Plan

A weaker version of this roadmap would have placed all four backlog items into one "ecosystem & scaling" milestone, as the brief explicitly warned against ("do NOT force these into one milestone"). This version instead:

1. Split them across two genuinely different tracks (Ecosystem: SDK, CLI; Scale: Distributed Metrics, Kubernetes) because they serve different audiences and have different risk profiles.
2. Sequenced the SDK before the CLI as a real, load-bearing dependency, not a stylistic ordering choice.
3. Took the backlog's own stated reasoning for Distributed Metrics ("only when Phase 7 includes horizontal scaling") literally and structurally, making it a genuine conditional dependency rather than a note that gets ignored once implementation starts.
4. Applied the same conditional-evidence discipline to Kubernetes, going further than the backlog's own text required, because the same reasoning that applies to Distributed Metrics applies at least as strongly to a full container-orchestration deployment path.
5. Added two new, non-backlog milestones (M1, M2) specifically because the roadmap brief asked for "meaningful platform capabilities" and "increased real-world usefulness, intelligence, explainability, research value" — and the four backlog items alone, while all individually justified, don't touch intelligence, explainability, or research value at all. A roadmap consisting only of the four deferred items would have satisfied the letter of the backlog instruction while missing the actual primary objective stated at the top of the brief.

---

# Part VII — Consolidated Verification Quick-Reference

*(New in this combined document — every milestone's acceptance bar gathered into one table for fast scanning, cross-referencing Parts II and VI.)*

| # | Concrete Acceptance Test | What Failing This Test Would Mean |
|---|---|---|
| M1 | A human reviewer can explain a real investigation's reasoning from the rendered trace alone, no raw logs. | Explainability is present in storage but not actually usable — the milestone's entire point unmet. |
| M2 | Planted-pattern fixture test passes; a real run produces at least one domain-plausible finding. | The mining logic either misses real signal or fabricates false patterns — both are disqualifying for a "research value" claim. |
| M3 | `pip install gaiaos-sdk` + notebook-style flow succeeds with zero raw HTTP code. | The SDK isn't actually sufficient for real usage, undermining the entire adoption rationale for building it. |
| M4 | First-time-contributor persona completes core flows using only `--help` and the CLI's own docs. | The CLI fails its core DX purpose — the reason it was built at all. |
| M5 | A clear, evidence-backed answer is produced either way. | The only failure mode is *not producing an honest answer* — building or not building infrastructure are both valid outcomes. |
| M6 | Existing SLO/dashboard tests pass **unmodified** against the new backend (if built). | Any modification required to existing tests would prove this wasn't a clean swap behind the existing interface. |
| M7 | k3s smoke test passes (if built), or formal deferral to Phase 8 with written rationale. | Same two-valid-outcomes structure as M5 — the only failure mode is skipping the decision itself. |
