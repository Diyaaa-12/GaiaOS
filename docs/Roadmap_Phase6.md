# GaiaOS — Phase 6 Engineering Design Document

**Role:** Distinguished Software Architect / AI Systems Architect / Platform Architect, five-year horizon.
**Status:** Phases 1–5 complete, frozen, v0.5.4. Nothing below redesigns them.
**Mission:** Phase 6 makes GaiaOS's intelligence real — powered by live, free, public environmental data, resilient to that data's inherent unreliability, and deployable end-to-end by a college student with nothing but Docker Compose.

---

## Part A — Architectural Review Before Milestone 1

### A.1 What's actually still "demo" after five phases (verified, not assumed)
Contrary to how it might read from the outside, GaiaOS's core domain agents have called **real, live public APIs since Phase 2** — USGS (seismic), NOAA (ocean), Open-Meteo (weather/geocoding), OpenAQ (air quality), FIRMS (wildfire). "Real data first" is Phase 6's *mission framing*, not a discovery that everything until now was fake. What remains genuinely demo-scoped, verified against the actual repository:
1. **The Literature/RAG corpus** — hand-seeded, not continuously ingested from a real open scientific-literature source.
2. **Historical hazard-event ingestion** covers exactly two sources (USGS, NOAA), per Phase 3's own deliberately-scoped "prove the pattern with two, more is trivial follow-on" decision — now the right phase to act on that follow-on.
3. **Simulation model parameters** — statistical models built in Phase 2 with illustrative, not historically-calibrated, coefficients.
4. **Region matching** — point-radius (`ST_DWithin`), not real administrative/geographic boundaries — a real geospatial simplification, not a demo per se, but a place where a free, standard dataset (OpenStreetMap) directly improves reasoning quality.
5. **No caching/retry/offline-degraded layer** — every external API call is a bare, single-attempt `httpx` request. This is the one gap Phase 6's own brief explicitly names, and it's real: verified, no retry decorator, no circuit breaker, no cache-on-failure path exists anywhere in `tools/`.

### A.2 The one hidden dependency that reorders everything else
**Every other Phase 6 milestone adds more calls to more free, public, rate-limited, occasionally-down external APIs.** Building any of them before the resilience layer (A.1.5) means building on the exact failure mode Phase 6's brief is most explicit about wanting solved ("support retries... support offline operation"). This is why the resilience layer is Milestone 1, not a cross-cutting concern bolted on later — the same lesson Phase 5's own pre-flight review applied to Redis-before-checkpointing, applied here to resilience-before-more-external-dependencies.

### A.3 Free-first audit of what Phase 6 is about to add
Every new data source named in the brief has a genuinely free tier or self-hosted option: USGS/NOAA/OpenAQ/FIRMS (already integrated, free, no key or free-tier key). Copernicus/Sentinel (free registration, EU public program, no cost). ERA5 (Copernicus Climate Data Store, free). GDELT (fully free, no key). OpenStreetMap (free Nominatim/Overpass, both self-hostable). NASA Earthdata (free with registration). **None of Phase 6's proposed sources require a paid tier at any milestone.** Where a hosted convenience option exists with a paid tier (e.g., a commercial Nominatim host), this document defaults to the self-hosted or public-free option and names the paid alternative only as an optional, non-default trade-off (ADR-601).

### A.4 Why six milestones, not more
The brief explicitly asks for fewer, well-designed milestones over milestone-count-maximizing. Six were chosen because each has a distinct, non-overlapping engineering payoff and a clean dependency shape (one root, one small independent hygiene item, four downstream beneficiaries of the root) — adding a seventh (e.g., a dedicated GDELT-only milestone) would have been splitting M2 for the sake of a bigger number, not for a real architectural boundary.

---

## Part B — Repository Impact Overview

```
gaiaos/
├── resilience/                    # NEW (M1) — sibling to cache/, metrics/: shared infra layer
│   ├── retry_policy.py             # tenacity-based retry/backoff, one shared config
│   ├── circuit_breaker.py          # per-source breaker state (Redis-backed, shared across workers)
│   └── degraded_mode.py            # the "serve stale + say so" contract
│
├── tools/
│   ├── copernicus_sentinel/        # NEW (M2)
│   ├── era5/                       # NEW (M2)
│   ├── gdelt/                      # NEW (M2)
│   └── osm_boundaries/             # NEW (M3)
│
├── ingestion/scheduled/hazard_event_sources/
│   ├── copernicus_wildfire.py      # NEW (M2)
│   └── era5_atmospheric.py         # NEW (M2)
│
├── ingestion/scheduled/literature_sources/   # NEW (M4)
│   └── arxiv_open_access.py
│
├── simulation_engine/
│   └── calibration/                 # NEW (M5) — parameter-fitting against real historical outcomes
│
├── ops/backup/
│   └── minio_storage.py             # NEW (M6) — a second BackupStorage implementation
│
└── db/models/
    └── administrative_boundary.py   # NEW (M3)
```
**Dependency direction:** `resilience/ → cache, config` only, imported by every `tools/*` client — the same "shared infra imported by many, importing from few" shape as `db/`, `cache/`, `metrics/` before it, not a new pattern.

---

## Part C — Milestones

### Milestone 1 — Resilience Layer: Caching, Retry, and Offline-Degraded Mode

**1. Goal:** every external tool call gets a shared retry policy, a per-source circuit breaker, and a defined degraded-mode contract (serve last-known-good cached data, explicitly labeled, rather than fail outright).
**2. Engineering motivation:** zero retry/cache/circuit-breaking exists today (A.1.5); every subsequent Phase 6 milestone adds more of exactly the dependency this gap is riskiest for.
**3. Product motivation:** a free public API being briefly down should degrade GaiaOS's answer quality, not its availability — a system that goes down whenever NOAA does isn't planetary-intelligence-grade.
**4. Dependencies:** none — root milestone.
**5. Scope:** `resilience/retry_policy.py` (shared `tenacity` config: exponential backoff, jitter, max 3 attempts), `resilience/circuit_breaker.py` (Redis-backed, per-source open/half-open/closed state, shared across worker replicas — reusing `cache/`'s existing Redis client, not a new connection), `resilience/degraded_mode.py` (wraps a tool call: on circuit-open, return last cached response with `uncertainty.source="data_sparsity"` and an explicit `degraded=True` flag propagated into `AgentOutput.errors` as an informational, non-fatal note); migrate all existing `tools/*` clients to route through this layer.
**6. Out of scope:** a general-purpose service mesh / sidecar proxy — this is application-level, in-process resilience, not infrastructure-level, matching this project's consistent preference for the simplest correct mechanism.
**7. Repository impact:** new `resilience/` package; every existing tool client modified to wrap its HTTP call.
**8. New modules:** as in point 5.
**9. Modified modules:** `tools/{seismic_usgs,ocean_noaa,weather,wildfire_firms,geocoding}.py`.
**10. Public APIs:** none new — internal only.
**11. Internal APIs:**
```python
async def resilient_call(source: str, fn: Callable[[], Awaitable[T]], cache_key: str, ttl: int) -> ResilientResult[T]: ...
class ResilientResult(Generic[T]):
    value: T
    degraded: bool
    source_status: Literal["live", "cached", "unavailable"]
```
**12. Data flow:** `Agent → tool client → resilient_call(source, fn, cache_key) → try fn() with retry → on exhaustion, check circuit → if open, serve cache (degraded=True) → if no cache and no live, source_status="unavailable"`.
**13. Sequence (text):**
```
OceanAgent -> ocean_noaa.get_readings: (station_id)
ocean_noaa -> resilient_call: (source="noaa", fn=<http call>, cache_key)
resilient_call -> CircuitBreaker: check state("noaa")
alt closed
  resilient_call -> NOAA API: attempt (up to 3, backoff)
  alt success
    resilient_call -> Cache: store(cache_key, result, ttl)
    resilient_call -> caller: ResilientResult(value, degraded=False, "live")
  else all attempts fail
    resilient_call -> CircuitBreaker: record_failure("noaa")
    resilient_call -> Cache: get(cache_key)
    alt cache hit
      resilient_call -> caller: ResilientResult(cached_value, degraded=True, "cached")
    else
      resilient_call -> caller: ResilientResult(None, degraded=True, "unavailable")
    end
  end
else open
  resilient_call -> Cache: get(cache_key) [skip live attempt entirely, per breaker state]
  resilient_call -> caller: [same cached/unavailable branch as above]
end
```
**14. Database impact:** none.
**15. Redis impact:** circuit-breaker state (`gaiaos:circuit:{source}`) and response cache (`gaiaos:cache:{source}:{key}`), both via the existing `RedisKeyBuilder` namespace.
**16. Background worker impact:** none new — this wraps existing synchronous-within-a-job tool calls.
**17. LangGraph impact:** none structural — `AgentOutput.errors` gains a documented, structured `degraded` entry shape rather than a free-text string, a small, additive schema refinement.
**18. AI agent impact:** every domain agent's evidence can now honestly carry "this is stale/cached data" — directly feeds Phase 5 M3's `UncertaintyEstimate.source="data_sparsity"`, a real, planned integration point, not a coincidence.
**19. Dataset impact:** none.
**20. Evaluation impact:** the eval benchmark set gains one question specifically run with a mocked-down external source, asserting the system still produces a degraded-but-honest answer rather than failing the whole investigation — the concrete way this milestone's value is measured, not just asserted.
**21. Security impact:** cached responses must respect the same trust boundary as live ones — cached evidence still flows through Synthesis's untrusted-data prompt framing (Phase 3), no new attack surface, but worth stating explicitly since it's easy to assume "it's just a cache" means "it's safe."
**22. Observability:** per-source circuit state, cache hit rate, degraded-response rate — natural additions to Phase 4's admin dashboard.
**23. Metrics:** `circuit_state{source}`, `cache_hit_rate{source}`, `degraded_response_rate{source}`.
**24. Performance:** cache hits are strictly faster than live calls — a genuine latency win on top of the resilience win.
**25. Scalability:** circuit-breaker state is Redis-backed specifically so it's shared correctly across horizontally-scaled workers (Phase 5 M7) — a worker-local-only breaker would let each replica independently hammer a down source.
**26. Reliability:** this milestone's entire point.
**27. Error handling:** `source_status="unavailable"` (no cache, source down) is the one case that must still surface as an honest `AgentOutput.errors` gap, not silently disappear — the existing Phase 2 gap-disclosure discipline extended, not replaced.
**28. Testing strategy:** unit — retry/backoff timing, circuit state transitions (closed→open→half-open) against a fixture clock. Integration — a real tool client wrapped in `resilient_call` against a deliberately-failing mock, asserting cache fallback and correct `degraded` flagging. Failure-path — no cache and source down → `unavailable`, correctly surfaced, not swallowed.
**29. CI/CD impact:** none structurally new.
**30. Documentation impact:** `docs/phase6/resilience.md`.
**31. Migration strategy:** none.
**32. Rollback strategy:** `resilient_call` can be bypassed via a settings flag reverting to Phase 5 bare-call behavior.
**33. Definition of Done:** the deliberately-failing-mock integration test (point 28) passes; the degraded-mode eval question (point 20) produces an honest, non-fatal answer.
**34. Risks:** cache staleness must have sane per-source TTLs (weather data stales faster than administrative boundaries) — configured per-source, not one global constant.
**35. Technical debt intentionally accepted:** no service-mesh-level resilience (point 6) — permanent, by design.
**36. Future extensibility:** every Phase 6 milestone from here on routes new tool clients through this layer by default, not as an afterthought.

**ADR-601: `tenacity` for Retry, a Custom Minimal Redis-Backed Breaker, Not a Full Resilience Framework**
*Decision:* `tenacity` (a small, well-established Python retry library) for backoff; a purpose-built ~50-line circuit breaker, not a library like `pybreaker` or a service mesh.
*Alternatives considered:* `pybreaker` (a real option, rejected only because its default in-process-only state doesn't share correctly across horizontally-scaled workers without extra wiring, and the custom Redis-backed version ends up similarly sized once that wiring is added anyway); a sidecar/service-mesh proxy (Envoy, Linkerd) — rejected outright, not a close call, as exactly the infrastructure-for-its-own-sake this project's design philosophy warns against for a Docker-Compose-deployable, free-first project.
*Why this wins:* smallest correct mechanism, consistent with every other infra decision in this project's history (Redis for the shared state it already uses for everything else, no new moving part).
*Future implications:* if GaiaOS ever needs cross-service (not just cross-worker-replica) circuit breaking, this decision would need revisiting — named as the condition, not assumed away.

---

### Milestone 2 — Multi-Source Environmental Data Ingestion Expansion

**1. Goal:** add Copernicus/Sentinel (wildfire/land-cover), ERA5 (atmospheric reanalysis baseline), and GDELT (socio-political hazard context) as real, scheduled, resilience-layer-wrapped data sources.
**2. Engineering motivation:** Phase 3 M8 proved the ingestion+scheduler pattern with two sources and explicitly deferred a third as "trivial follow-on" — this is that follow-on, done properly, for three sources at once since the pattern is now proven and the marginal cost per source is genuinely small.
**3. Product motivation:** Copernicus/ERA5 directly feed Milestone 5's simulation calibration with real atmospheric baselines instead of arbitrary constants; GDELT gives the Causal Chain agent a socio-political-event dimension (evacuations, infrastructure failures reported in open news data) that pure physical-hazard sources can't provide — a genuine, new reasoning capability, not just more of the same data type.
**4. Dependencies:** Milestone 1 (every new source must be resilience-wrapped from day one, per A.2).
**5. Scope:** three new `IngestionCursor`-tracked sources, following Phase 3 M8's exact established pattern (dedup by source+external_id, cursor-based incremental fetch, scheduled worker job).
**6. Out of scope:** Sentinel *imagery* processing (raster analysis, object detection on satellite images) — genuinely out of scope for this milestone, which ingests Sentinel's structured hazard/land-cover *metadata* products, not raw imagery; full remote-sensing image analysis is a materially larger, separately-justified future capability, not folded in here to avoid scope bloat.
**7. Repository impact:** `tools/{copernicus_sentinel,era5,gdelt}/`, `ingestion/scheduled/hazard_event_sources/{copernicus_wildfire,era5_atmospheric}.py`, `workers/jobs/ingestion_jobs.py` extended.
**8. New modules:** as above.
**9. Modified modules:** `workers/scheduler.py` (three new registered jobs), `orchestrator/agents/causal_chain/agent.py` (GDELT-sourced events become a new `hazard_events.event_type` category).
**10. Public APIs:** none new.
**11. Internal APIs:** `fetch_recent_copernicus_events`, `fetch_recent_era5_baseline`, `fetch_recent_gdelt_events` — each mirroring Phase 3 M8's `fetch_recent_X_events(since: datetime) -> list[HazardEventRecord]` signature exactly, no new shape invented.
**12. Data flow:** identical to Phase 3 M8's established ingestion flow (§ that milestone's own data-flow diagram), for three new sources.
**13. Sequence (text):** identical in shape to Phase 3 M8, omitted here to avoid repeating an already-established, unchanged pattern verbatim.
**14. Database impact:** `hazard_events.event_type` gains new values (`wildfire_satellite`, `atmospheric_anomaly`, `civil_unrest_hazard_adjacent`); no schema change beyond what Phase 3/5's existing tables already support.
**15. Redis impact:** covered entirely by Milestone 1's resilience layer.
**16. Background worker impact:** three new scheduled job registrations, same mechanism as every prior scheduled job.
**17. LangGraph impact:** none structural.
**18. AI agent impact:** Causal Chain agent's reasoning genuinely broadens (GDELT); Simulation agent gains a real baseline input (ERA5) it didn't have before.
**19. Dataset impact:** Phase 5 M9's published dataset export gains three new event types — additive, no anonymization-policy change needed (all three sources are already-public data, same trust tier as USGS/NOAA).
**20. Evaluation impact:** at least one new benchmark question per source, following Phase 5 M1's real-metrics discipline.
**21. Security impact:** GDELT specifically ingests open-web-sourced event data — apply the same untrusted-content prompt framing (Phase 3) to any GDELT-derived text reaching an LLM prompt, since news-sourced text is meaningfully less curated than a government science agency's structured API.
**22. Observability:** per-source ingestion success rate, records-per-run — extends Phase 3 M8's existing metrics shape.
**23. Metrics:** as above, per new source.
**24. Performance:** bounded by resilience layer's retry/backoff; no new performance concern.
**25. Scalability:** scheduled, incremental, cursor-based — same bounded-cost shape as existing ingestion.
**26. Reliability:** inherits Milestone 1's guarantees by construction.
**27. Error handling:** identical pattern to Phase 3 M8 — failed run doesn't advance cursor, safe retry next cycle.
**28. Testing strategy:** unit — dedup logic per source. Integration — `respx`-mocked source responses driving full ingestion jobs, matching Phase 3's established test pattern exactly.
**29. CI/CD impact:** none structurally new.
**30. Documentation impact:** `docs/phase6/data_sources.md` — field-mapping per source, same discipline as Phase 3 M8's documentation requirement.
**31. Migration strategy:** none (event_type is a free-text/enum-extensible column, not requiring a schema migration per new value).
**32. Rollback strategy:** each source individually toggleable via `Settings` (`INGESTION_ENABLE_{SOURCE}`), matching Phase 3's per-source enable/disable design.
**33. Definition of Done:** a real (manually-verified-once) ingestion run against live Copernicus/ERA5/GDELT endpoints populates real, deduplicated `hazard_events` rows.
**34. Risks:** GDELT's volume is much higher than USGS/NOAA's — cursor/pagination must handle this explicitly, tested against a realistic-volume fixture, not just a handful of rows.
**35. Technical debt intentionally accepted:** no Sentinel imagery analysis (point 6) — real future work, not a gap in this milestone.
**36. Future extensibility:** a fourth/fifth source (NASA Earthdata, Copernicus's other data products) is now a drop-in addition to a five-source-proven pattern.

---

### Milestone 3 — OpenStreetMap-Based Administrative Boundary Resolution

**1. Goal:** replace point-radius (`ST_DWithin`) region matching with real administrative-boundary polygons from OpenStreetMap, self-hosted Nominatim (or the free public instance for low-volume/dev use).
**2. Engineering motivation:** a circle around a point is a crude proxy for "this region" — real administrative boundaries (a city, a coastal province) are what causal reasoning about regional hazard correlation actually means.
**3. Product motivation:** "earthquakes affecting the same province as this flood" is a materially better question than "earthquakes within 50km of this point," and OSM is free, standard, and already PostGIS-native-compatible.
**4. Dependencies:** Milestone 1 (Nominatim/Overpass calls go through the resilience layer like every other external source).
**5. Scope:** `db/models/administrative_boundary.py` (a `GEOMETRY(MultiPolygon, 4326)` table, seeded from OSM boundary extracts for the regions the existing hazard sources actually cover — not a full-planet import, which would be a large, low-value data-volume decision for a project this stage); `tools/osm_boundaries/` (Nominatim/Overpass client, resilience-wrapped); `db/causal_repository.py`'s query gains an optional `ST_Within(point, boundary.geom)` mode alongside the existing radius mode — additive, not a replacement, since radius queries remain correct and useful for point-source hazards without a natural boundary (e.g., "near this specific reactor").
**6. Out of scope:** a full-planet OSM import (multi-hundred-GB, wildly disproportionate to this project's actual data footprint); real-time OSM edit-stream syncing (a static, periodically-refreshed extract is the right cadence for administrative boundaries, which change on the order of years, not minutes).
**7. Repository impact:** `db/models/administrative_boundary.py`, `tools/osm_boundaries/`, `data/migrations/versions/00XX_administrative_boundaries.py`.
**8. New modules:** as above.
**9. Modified modules:** `db/causal_repository.py`, `orchestrator/agents/causal_chain/agent.py`.
**10. Public APIs:** none new.
**11. Internal APIs:**
```python
async def resolve_boundary(lat: float, lon: float) -> AdministrativeBoundary | None: ...
async def find_causal_chain_within_boundary(event_type: str, boundary_id: UUID, max_depth: int = 4) -> list[Evidence]: ...
```
**12. Data flow:** `geocode(location) → (lat, lon) → resolve_boundary(lat, lon) [cached, boundaries change rarely] → CausalChainAgent uses boundary polygon instead of / alongside radius`.
**13. Sequence (text):**
```
CausalChainAgent -> geocoding: geocode(location)
CausalChainAgent -> osm_boundaries: resolve_boundary(lat, lon)
osm_boundaries -> resilient_call: (source="osm", fn=<Nominatim reverse geocode>, long TTL cache)
osm_boundaries -> CausalChainAgent: AdministrativeBoundary(id, geom, name)
CausalChainAgent -> causal_repository: find_causal_chain_within_boundary(event_type, boundary.id)
causal_repository -> Postgres: WITH RECURSIVE ... WHERE ST_Within(he.region, :boundary_geom) ...
```
**14. Database impact:** new `administrative_boundaries` table with a GIST index — the second real PostGIS use case in this project, alongside `hazard_events.region`.
**15. Redis impact:** boundary lookups cached with a long TTL (weeks), via Milestone 1's resilience layer.
**16. Background worker impact:** none new — boundary resolution happens inline, cached aggressively given how rarely boundaries change.
**17. LangGraph impact:** none structural.
**18. AI agent impact:** Causal Chain reasoning quality improvement, directly measurable via Phase 5 M1's real eval metrics.
**19. Dataset impact:** boundary polygons are OSM's own open data (ODbL-licensed) — the attribution requirement must be stated in `docs/phase6/data_sources.md` and, if boundary-derived findings are ever included in Phase 5 M9's public dataset export, in that export's own license/attribution metadata.
**20. Evaluation impact:** benchmark questions comparing radius-mode vs. boundary-mode causal-chain results for the same real scenario — a direct, measured "did this actually improve reasoning quality" check, not assumed.
**21. Security impact:** none beyond standard resilience-layer coverage.
**22. Observability:** boundary-cache hit rate.
**23. Metrics:** as above.
**24. Performance:** `ST_Within` against a GIST-indexed polygon column is comparable in cost to `ST_DWithin` — no meaningful performance regression.
**25. Scalability:** boundary data volume is small and static (regions actually covered by existing hazard sources, not the whole planet) — bounded by design (point 6).
**26. Reliability:** boundary resolution failure falls back to the existing radius-mode query, never a hard failure — an explicit, tested fallback.
**27. Error handling:** consistent with every other resilience-layer-wrapped source.
**28. Testing strategy:** unit — `ST_Within` query construction. Integration — seeded fixture boundary + events, asserting boundary-mode correctly includes/excludes events a radius-mode query would get wrong (e.g., a long, thin coastal province where a 50km radius circle both misses part of the province and includes an adjacent one) — the concrete proof this milestone delivers real value over the status quo, not just a stylistic change.
**29. CI/CD impact:** none structurally new.
**30. Documentation impact:** `docs/phase6/geospatial_boundaries.md`, OSM/ODbL attribution note.
**31. Migration strategy:** standard Alembic migration + a one-time seed script for the initially-covered regions.
**32. Rollback strategy:** radius mode remains fully functional and is the automatic fallback — boundary mode can be disabled via settings with zero effect on existing behavior.
**33. Definition of Done:** the coastal-province fixture test (point 28) passes, demonstrating boundary-mode's correctness advantage concretely, not just conceptually.
**34. Risks:** OSM boundary data quality varies by region — document this honestly rather than presenting boundary-mode as uniformly authoritative everywhere.
**35. Technical debt intentionally accepted:** no full-planet coverage, no real-time sync (point 6) — permanent, by design, scoped to actual need.
**36. Future extensibility:** the boundary table's structure supports adding polygon-overlap queries (fire perimeters, flood extents) later, which was Architecture v1.0's own original, not-yet-realized PostGIS justification.

**ADR-602: Self-Hosted Nominatim (Optional) Over the Public Nominatim Instance (Default for Small Deployments)**
*Decision:* default to the free public Nominatim usage-policy-compliant endpoint for low-volume/dev deployments; document self-hosted Nominatim (a standard, well-documented Docker image) as the recommended path once a deployment's query volume would strain the public instance's fair-use policy.
*Alternatives considered:* mandating self-hosted Nominatim from day one (rejected: real, non-trivial resource cost — a self-hosted Nominatim instance needs meaningful disk/RAM for planet-extract processing — disproportionate for a college-student-scale deployment doing a handful of lookups a day); a paid geocoding API (rejected outright per the free-first mandate).
*Why this wins:* genuinely free at small scale, with a documented, self-hosted upgrade path at real scale — exactly the tiered, honest trade-off the brief asks this document to make explicit whenever a "free vs. more capable" choice exists.
*Future implications:* the `tools/osm_boundaries/` client's base URL is `Settings`-configurable specifically so switching from public to self-hosted Nominatim later is a config change, not a code change.

---

### Milestone 4 — Real Literature Corpus Ingestion Pipeline

**1. Goal:** replace the hand-seeded literature fixture corpus with a scheduled, real, licensing-respecting ingestion pipeline from open-access scientific literature (arXiv's open-access physical-sciences/earth-science categories as the concrete first source).
**2. Engineering motivation:** the Literature/RAG agent's entire value proposition depends on the corpus being real and current; a static fixture set was always explicitly scoped as a placeholder pending exactly this milestone.
**3. Product motivation:** grounding claims in continuously-updated, real scientific literature is a direct, measurable reasoning-quality improvement, evaluable via Phase 5 M1's now-real retrieval-precision metric.
**4. Dependencies:** Milestone 1 (arXiv's API, like every external source, goes through the resilience layer).
**5. Scope:** `ingestion/scheduled/literature_sources/arxiv_open_access.py` — scheduled fetch of new open-access earth/environmental-science papers, chunked, embedded, inserted into the existing `literature_chunks` table (Phase 3's schema, unchanged).
**6. Out of scope:** paywalled/closed-access literature (Elsevier, Springer APIs) — explicitly excluded, not because they're technically hard, but because they're licensing-incompatible with the free-first, openly-reusable-dataset mandate this phase is built around; a full citation-graph/impact-ranking system — a real future capability, not this milestone's job, which is ingestion, not literature-quality ranking.
**7. Repository impact:** `ingestion/scheduled/literature_sources/`.
**8. New modules:** as above.
**9. Modified modules:** `workers/scheduler.py` (new registered job), `orchestrator/agents/literature_rag/agent.py` (no logic change — it already consumes `literature_chunks` however populated, proving the Phase 3 design's clean separation between retrieval logic and corpus population actually pays off here).
**10. Public APIs:** none new.
**11. Internal APIs:** `fetch_new_arxiv_papers(since: datetime, categories: list[str]) -> list[PaperRecord]`.
**12. Data flow:** `Scheduler → fetch_new_arxiv_papers → chunk → embed → dedupe by arxiv_id → INSERT literature_chunks`.
**13. Sequence (text):**
```
Scheduler -> literature_ingestion_job: run()
literature_ingestion_job -> IngestionCursor: get_last_run("arxiv")
literature_ingestion_job -> arxiv_open_access: fetch_new_arxiv_papers(since, categories=["physics.ao-ph", "physics.geo-ph"])
arxiv_open_access -> resilient_call: (source="arxiv", ...)
literature_ingestion_job -> chunker: chunk(paper.abstract_and_body)
literature_ingestion_job -> embedding_model: embed(chunks)
literature_ingestion_job -> Postgres: dedupe by arxiv_id, INSERT literature_chunks
literature_ingestion_job -> IngestionCursor: update_last_run("arxiv", now())
```
**14. Database impact:** `literature_chunks` gains a `source_id` (arXiv ID) column for dedup — additive.
**15. Redis impact:** covered by Milestone 1.
**16. Background worker impact:** the fifth scheduled-job type in this project's history (ingestion, alerting, backup, dataset export, now literature) — sixth if Milestone 2's three new sources are each counted as registrations of the same job *type*, which they are, not new mechanisms.
**17. LangGraph impact:** none — proves the Phase 3 corpus/retrieval separation design decision was correct.
**18. AI agent impact:** Literature/RAG agent's grounding quality, directly measurable.
**19. Dataset impact:** none beyond what already exists.
**20. Evaluation impact:** retrieval-precision (Phase 5 M1, now real) becomes trackable over time as the corpus grows — a genuinely interesting, real trend line this project has never had before.
**21. Security impact:** ingested paper text flows into LLM prompts as evidence — already covered by Phase 3's untrusted-content framing, no new gap, but worth re-confirming this specific new content type is covered, not assumed.
**22. Observability:** corpus growth rate, per-category ingestion volume.
**23. Metrics:** as above.
**24. Performance:** embedding generation is the real cost here — batched, rate-limited via the resilience layer's retry/backoff, not a burst that could overwhelm the embedding provider.
**25. Scalability:** corpus growth is exactly the scale dimension Architecture v1.0's own Qdrant-migration trigger (>10-20M chunks) was defined against — this milestone is the first thing in this project's history that could plausibly, eventually, approach that trigger; worth a note in the milestone's own documentation, not acted on now.
**26. Reliability:** inherits Milestone 1.
**27. Error handling:** consistent with existing ingestion patterns.
**28. Testing strategy:** unit — dedup by `source_id`. Integration — `respx`-mocked arXiv responses through a full ingestion cycle, chunking and embedding verified against known fixture text.
**29. CI/CD impact:** none structurally new.
**30. Documentation impact:** `docs/phase6/literature_ingestion.md`, explicit licensing note (arXiv open-access terms).
**31. Migration strategy:** standard Alembic migration for `source_id`.
**32. Rollback strategy:** disable via settings flag; existing corpus (fixture or previously-ingested) remains queryable regardless.
**33. Definition of Done:** a real ingestion run against live arXiv populates genuine new chunks, correctly deduplicated on a second run.
**34. Risks:** arXiv content quality/relevance varies — not every physics.ao-ph paper is relevant to planetary risk; a coarse category-filter is the v1 relevance mechanism, with retrieval-precision tracking (point 20) as the ongoing quality signal, not a one-time judgment.
**35. Technical debt intentionally accepted:** category-level filtering only, no fine-grained relevance pre-screening (point 6's citation-ranking exclusion) — real future work.
**36. Future extensibility:** the same `fetch_new_X_papers` pattern extends to additional open-access sources (NOAA technical reports, IPCC assessment reports where openly licensed) as low-risk, drop-in follow-ons.

---

### Milestone 5 — Simulation Model Calibration Against Real Historical Data

**1. Goal:** fit Simulation agent model parameters (Phase 2's statistical models — plume dispersion, flood extent, wildfire spread, ENSO forecasting) against real historical outcomes now available from Phase 3/6's real hazard-event and ERA5 data, replacing illustrative constants.
**2. Engineering motivation:** this is the concrete payoff of every ingestion investment in this phase — real data existing is only valuable if it makes the system's actual predictions better, and this is the milestone that closes that loop.
**3. Product motivation:** the single most direct "planetary risk problems using real environmental data" deliverable in this entire document.
**4. Dependencies:** Milestone 2 (ERA5 atmospheric baseline, real Copernicus wildfire outcomes as calibration targets).
**5. Scope:** `simulation_engine/calibration/` — offline (not query-time) parameter-fitting scripts, run periodically (not per-investigation), producing versioned parameter sets the Simulation models load at startup; a calibration-quality report (predicted vs. actual, against held-out historical events) as the concrete verification artifact.
**6. Out of scope:** online/continuous learning (parameters updating during live query serving) — deliberately offline, versioned, and reviewable, matching this project's consistent preference for explainable, auditable behavior over adaptive-but-opaque behavior; a full physics-based simulation upgrade — still, correctly, off the table, unchanged from every prior phase's position.
**7. Repository impact:** `simulation_engine/calibration/`.
**8. New modules:** `simulation_engine/calibration/{fit_wildfire_spread,fit_flood_extent,fit_plume_dispersion,fit_enso_forecast}.py`, `simulation_engine/calibration/report.py`.
**9. Modified modules:** `simulation_engine/models/*.py` (load calibrated parameters from a versioned config file rather than hardcoded constants).
**10. Public APIs:** none new.
**11. Internal APIs:** `fit_parameters(model_name: str, historical_events: list[HazardEventRecord]) -> CalibratedParameterSet`.
**12. Data flow:** `[offline, scheduled monthly] → pull real historical hazard_events + ERA5 baseline → fit_parameters → CalibratedParameterSet(version, fitted_at, parameters, validation_report) → written to a versioned config → SimulationAgent loads latest at next worker restart`.
**13. Sequence (text):**
```
Scheduler (monthly) -> calibration_job: run()
calibration_job -> Postgres: SELECT historical hazard_events + ERA5 baseline
calibration_job -> fit_parameters: (model_name, historical_data)
fit_parameters -> calibration_job: CalibratedParameterSet
calibration_job -> report: validate against held-out events
calibration_job -> config/simulation_parameters/{model}_v{N}.yaml: write, versioned
calibration_job -> metrics: emit(CalibrationCompleted, validation_score)
[at next worker startup]
SimulationAgent -> config: load latest calibrated parameters
```
**14. Database impact:** none — parameters live in versioned config files (git-trackable, reviewable), not the database, deliberately (point 6's "explainable, auditable" reasoning).
**15. Redis impact:** none.
**16. Background worker impact:** the calibration job is the sixth scheduled-job type, reusing the established mechanism.
**17. LangGraph impact:** none.
**18. AI agent impact:** Simulation agent's `uncertainty_bounds` should genuinely narrow (more confident, correctly) for well-calibrated model/region combinations, and this should be visible in Phase 5 M1's real calibration metric over time — the single clearest, most measurable "AI reasoning quality" improvement in this entire roadmap.
**19. Dataset impact:** the calibration validation report itself is a genuinely interesting artifact worth including in Phase 5 M9's public research API/dataset — external researchers can independently assess model quality, not just trust GaiaOS's own claims about it.
**20. Evaluation impact:** the eval benchmark set gains simulation-heavy questions with real, known historical outcomes as ground truth — the calibration/ECE metric (Phase 5 M1) becomes directly meaningful here for the first time (previously it had little simulation-specific signal to measure).
**21. Security impact:** none.
**22. Observability:** calibration run success/validation-score trend.
**23. Metrics:** `simulation_calibration_validation_score{model}`.
**24. Performance:** calibration itself is offline/monthly, zero query-time cost.
**25. Scalability:** none.
**26. Reliability:** a failed/degenerate calibration run must never silently replace good parameters with bad ones — the validation report (point 5) is a hard gate: a new parameter set only gets promoted to "latest" if its held-out validation score is at least as good as the current one, tested explicitly.
**27. Error handling:** insufficient historical data for a given model/region → calibration run skips that combination, logs why, keeps prior parameters — never falls back to un-calibrated defaults silently.
**28. Testing strategy:** unit — the promotion-gate logic (point 26) against a deliberately-worse fixture parameter set, asserting it's correctly rejected. Integration — a full calibration run against seeded historical fixture data with a known-correct expected parameter range.
**29. CI/CD impact:** none structurally new; calibration config changes go through normal PR review, matching Milestone 8-of-Phase-5's config-as-code precedent for consequential, infrequent decisions.
**30. Documentation impact:** `docs/phase6/simulation_calibration.md` — the fitting methodology per model, in enough detail that a domain scientist reviewing this project could assess it, not just a software engineer.
**31. Migration strategy:** none (config files, not schema).
**32. Rollback strategy:** any previous versioned parameter file can be reactivated by config change alone, no code deploy needed.
**33. Definition of Done:** the promotion-gate rejection test (point 28) passes; a real calibration run against real historical data produces a validation report showing genuine improvement over the pre-Phase-6 illustrative constants for at least one model.
**34. Risks:** overfitting to historical data is a real statistical risk for any calibration exercise — the held-out validation split (point 5) is the direct, necessary defense, and must be a genuine held-out set, not data the fitting process has already seen, tested explicitly for this property.
**35. Technical debt intentionally accepted:** no online learning, no physics-based upgrade (point 6) — both permanent, by design.
**36. Future extensibility:** `CalibratedParameterSet`'s versioned-config pattern is the template for any future model needing the same "improve offline, promote only if validated, roll back trivially" discipline.

**ADR-603: Offline, Versioned, Config-File Calibration — Not Online Learning**
*Decision:* parameters are fit offline on a schedule and loaded from versioned config, never updated during live query serving.
*Context:* an online-learning approach (parameters drifting continuously based on incoming query outcomes) was a real alternative, common in ML-heavy systems.
*Alternatives considered:* online/continuous learning — rejected because it directly conflicts with this project's explainability commitment (Architecture v1.0's core value proposition since Phase 1): a parameter set that changed silently, continuously, based on live traffic would make "why did the system predict this" a moving target, undermining the execution-trace-based explainability this entire project is built around.
*Why offline wins:* every parameter change is a reviewable, versioned, git-diffable artifact — consistent with the config-as-code precedent already set by Phase 5 M8's SLO definitions, applied here to an even higher-stakes decision (what the system predicts, not just when it alerts).
*Future implications:* if genuinely adaptive, real-time-learning simulation ever becomes a stated goal, it would need its own explainability story built first — not assumed to fall out of this decision for free.

---

### Milestone 6 — MinIO Self-Hosted Object Storage Option

**1. Goal:** add MinIO (S3-compatible, self-hosted, free) as an optional `BackupStorage`/dataset-export target alongside the existing `LocalBackupStorage` default.
**2. Engineering motivation:** Phase 4 M6 deliberately kept backup storage local-filesystem-first and object-storage-optional; MinIO is the named, free-first way to actually exercise that optional path without requiring paid cloud, closing a gap that's existed since Phase 4.
**3. Product motivation:** a college-student deployment on a single VPS benefits from off-host backup durability without needing an AWS account — MinIO running as a seventh Docker Compose service is exactly the free-first answer.
**4. Dependencies:** none — independent, can run in parallel with every other Phase 6 milestone.
**5. Scope:** `ops/backup/minio_storage.py` (a second `BackupStorage` implementation, same interface Phase 4 M6 already defined — this milestone proves that interface was genuinely storage-backend-agnostic, not accidentally local-filesystem-coupled); a `minio` service added to `docker-compose.yml`, off by default (opt-in via a Compose profile, not a mandatory seventh always-running service for deployments that don't want it).
**6. Out of scope:** any actual paid cloud object storage integration (S3/GCS/Azure Blob) — explicitly, per the free-first mandate, not built in this milestone or assumed as a "real" production path; MinIO *is* the production-capable answer for this project's stated deployment philosophy, not a lesser stand-in for a "real" cloud option.
**7. Repository impact:** `ops/backup/minio_storage.py`, `docker-compose.yml` (new optional service).
**8. New modules:** `ops/backup/minio_storage.py`.
**9. Modified modules:** `ops/backup/postgres_backup.py`, `restore_drill.py`, `dataset_export_job.py` (all three gain a storage-backend parameter, defaulting to the existing `LocalBackupStorage`).
**10. Public APIs:** none new.
**11. Internal APIs:**
```python
class MinIOBackupStorage(BackupStorage):   # implements Phase 4 M6's existing interface
    async def upload(self, local_path: Path, remote_key: str) -> str: ...
    async def download(self, remote_key: str, local_path: Path) -> None: ...
```
**12. Data flow:** identical to Phase 4 M6's existing backup/restore-drill flow, with `storage_backend` swapped from `LocalBackupStorage` to `MinIOBackupStorage` when `Settings.BACKUP_STORAGE_BACKEND=minio` is configured.
**13. Sequence (text):** unchanged from Phase 4 M6's own sequence diagram, storage backend substituted — the direct proof this milestone is a clean extension, not a parallel new system.
**14. Database impact:** none.
**15. Redis impact:** none.
**16. Background worker impact:** none new — same backup/export jobs, different storage target.
**17. LangGraph impact:** none.
**18. AI agent impact:** none.
**19. Dataset impact:** Phase 5 M9's dataset export can now optionally publish to a self-hosted MinIO bucket with public read access, a genuine, free way to serve the published dataset without needing any paid hosting.
**20. Evaluation impact:** none.
**21. Security impact:** MinIO credentials are a new secret (access key/secret key) — validated non-empty when `BACKUP_STORAGE_BACKEND=minio`, same `model_validator` pattern used for every other conditionally-required setting since Phase 1.
**22. Observability:** none beyond what backup/export jobs already emit.
**23. Metrics:** none new.
**24. Performance:** local-network MinIO (same-host or same-LAN) is fast; a remote MinIO instance's performance is a deployment-specific concern, documented, not engineered around in this milestone.
**25. Scalability:** none — this is a storage-backend swap, not a new scaling dimension.
**26. Reliability:** the restore-drill mechanism (Phase 4 M6) must be re-run and verified against MinIO specifically, not assumed to work identically just because the interface is shared — an explicit, named test requirement, not an assumption.
**27. Error handling:** MinIO connection failure → the same fail-loud pattern Phase 4 M6 already established for backup failures (alerted, never silently skipped).
**28. Testing strategy:** integration — a real (test) MinIO container in CI (trivial to add — MinIO ships an official, lightweight Docker image), full backup→restore-drill cycle run against it, proving the storage-agnostic interface genuinely works, not just compiles.
**29. CI/CD impact:** new `minio` test service in the CI Compose stack.
**30. Documentation impact:** `ops/runbooks/minio_setup.md` — how to stand up MinIO for a self-hosted deployment, the direct, practical deliverable for the "college student on a VPS" persona this entire phase is framed around.
**31. Migration strategy:** none.
**32. Rollback strategy:** trivial — unset `BACKUP_STORAGE_BACKEND`, reverts to local storage with zero data loss for anything already backed up locally.
**33. Definition of Done:** the MinIO-backed restore-drill integration test (point 28) passes, proving genuine backend-agnosticism, not just interface compliance on paper.
**34. Risks:** none significant — this is a well-scoped, low-risk extension of an already-abstracted interface.
**35. Technical debt intentionally accepted:** no paid cloud object storage support (point 6) — permanent, by design, not a gap.
**36. Future extensibility:** if a deployment ever does need paid cloud object storage (e.g., a large institutional deployment with existing AWS infrastructure), the `BackupStorage` interface already supports adding an S3-native implementation as a third option without touching anything else — explicitly not built now, since nothing in this project's stated audience needs it yet.

---

## Part D — After All Milestones

### D.1 Overall Phase 6 Architecture
Milestone 1 is the sole root; Milestones 2, 3, and 4 are its direct, parallel-after-M1 beneficiaries (each adds real data through the same hardened path); Milestone 5 is the payoff, consuming Milestone 2's real data to make the system's actual predictions better; Milestone 6 is fully independent free-first infrastructure hygiene. No milestone this phase touches the Reasoning Core's graph shape, the Platform Services layer, or any frozen Phase 1–5 architecture — every change is either a new leaf (new tool clients, new ingestion sources) or a parameter/config swap (calibrated simulation parameters, storage backend), consistent with the brief's explicit instruction not to redesign completed phases.

### D.2 Updated System Diagram
```
                         Resilience Layer (M1)
                    (wraps every external call, all sources)
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                        │                          │
  Multi-Source Ingestion   OSM Boundaries (M3)      Literature Corpus (M4)
       (M2)                                                  │
        │                                                    │
        └──────────────┬─────────────────────────────────────┘
                        │
              Simulation Calibration (M5)
                        │
              [feeds back into Reasoning Core, unchanged shape]

  MinIO Storage (M6) — independent, plugs into existing Backup/Dataset-Export interfaces (Phase 4/5)
```

### D.3 Subsystem Dependency Graph
`resilience/` is now a dependency of every module in `tools/` and `ingestion/` — the single most-depended-on new module this phase introduces, by design (A.2).

### D.4 Milestone Dependency Graph
`M1 → {M2, M3, M4}`; `M2 → M5`; `M6` independent.

### D.5 Critical Implementation Order
**M1 → M2 → M3 → M4 → M5 → M6** (single engineer) — M6 placed last only because it's lowest-risk and most independent, giving a natural wind-down; it could equally run first or in parallel without violating any dependency. Two engineers: one takes M1 → M2 → M5, the other takes M3, M4, M6 in parallel once M1 lands.

### D.6 Risks of Incorrect Ordering
Any of M2/M3/M4 before M1 means new external dependencies added with zero retry/cache/circuit-breaking — directly reintroducing the exact fragility this phase's brief is most explicit about wanting solved. M5 before M2 means calibrating against the same limited two-source historical data Phase 3 always had, missing this phase's actual point.

### D.7 Future Technical Debt (Named, Not Hidden)
No Sentinel imagery/raster analysis (M2). No paywalled-literature ingestion (M4, by design, licensing-driven). No online/continuous simulation learning (M5, by design, explainability-driven). No full-planet OSM coverage (M3, by design, scope-driven). No paid cloud object storage (M6, by design, mission-driven). Every item here is named, permanent-until-a-new-reason, and cross-referenced to the milestone that made the call — none are silent gaps.

### D.8 Phase 7 Prerequisites
Real corpus growth data (M4) is the concrete input for deciding whether the Qdrant-migration trigger is finally approaching. Real calibration validation trends (M5) determine whether a genuinely more sophisticated (still explainable) simulation approach is justified. MinIO adoption data (M6) — how many real deployments actually use it — is the honest signal for whether further self-hosted-storage investment is worth it.

### D.9 Updated Long-Term Roadmap
Phase 1: foundation. Phase 2: reasoning core. Phase 3: trust infrastructure. Phase 4: operational maturity and open-source readiness. Phase 5: reasoning honesty, collaboration, responsible external exposure. Phase 6: real-world data grounding, resilience, and calibrated prediction quality, entirely on free infrastructure. The mission framing changes each phase; the discipline — smallest correct thing, real verification, named honest deferrals — does not, for the sixth consecutive time.

### D.10 Production Readiness Assessment
Post-Phase-6, GaiaOS is a system whose external data dependencies are resilient rather than brittle, whose literature grounding is real and current rather than static, whose predictions are calibrated against real historical outcomes rather than illustrative, and whose entire stack — including now backup/dataset storage — remains genuinely, fully deployable on free and self-hosted infrastructure. This is the point at which "planetary intelligence platform" stops being a phrase this project has earned the right to use only aspirationally.

---

## Part E — Verification, Exit Criteria, and Checklists

### E.1 Verification Summary
Every milestone's Part C entry specifies its own unit/integration tests and CI additions. Two carry the most consequential verification burden: **M5's promotion-gate rejection test** (a bad calibration must never silently replace good parameters) and **M6's MinIO-backed restore drill** (proving genuine backend-agnosticism, not assumed interface compliance) — both should receive proportionally more review attention than their scope would otherwise suggest.

### E.2 Phase 6 Exit Criteria
- M1's degraded-mode eval question produces an honest, non-fatal answer under a simulated source outage.
- M2's three new sources each show a real, verified (not just mocked) successful ingestion run.
- M3's coastal-province boundary-vs-radius fixture test demonstrates a concrete correctness improvement.
- M4's real arXiv ingestion run populates genuine, deduplicated new corpus content.
- M5's promotion-gate correctly rejects a deliberately-worse calibration and a real calibration run shows measured improvement over pre-Phase-6 constants.
- M6's MinIO-backed restore drill passes.

### E.3 Engineering Review Checklist
Every new external source (M2, M3, M4) routes through the resilience layer (M1) — verified by code review, not assumed by convention.

### E.4 Engineering Audit Checklist
1. Re-verify every carried-forward prior finding, per this engagement's now-established practice across five prior audits.
2. Independently trigger a circuit-open condition (M1) against a real source and confirm degraded-mode behavior, not just the mocked test.
3. Independently inspect a real calibration validation report (M5) for evidence of held-out-set discipline, not just trust the promotion gate's own pass/fail.
4. Independently verify MinIO credentials (M6) are never logged, mirroring the same secret-hygiene check applied to every credential this project has added since Phase 1.

### E.5 Operational Readiness Checklist
Per-source circuit-breaker dashboards (M1) are visible on the existing admin dashboard (Phase 4 M9); scheduled-job health (now six job types) is monitored uniformly, not source-by-source ad hoc; a real deployment can choose local-only or MinIO-backed backup storage with an equally-documented, equally-supported path for both.

### E.6 Production Readiness Checklist
All prior-phase criteria (Phase 4 E.3, Phase 5 E.4) hold, plus: the system degrades honestly rather than fails when any single free public data source is unavailable, and every new capability this phase added remains deployable with zero paid infrastructure, verified by the absence of any mandatory paid-service dependency in the final `docker-compose.yml` and `requirements/` — checked directly, not assumed.

### E.7 Open Source Readiness Checklist
`docs/phase6/data_sources.md` gives a new contributor a single, current reference for every data source this project depends on and its licensing terms — directly extending the documentation-discoverability standard Phase 4/5 established, applied to this phase's genuinely new category of dependency (external data licensing) for the first time in this project's history.
