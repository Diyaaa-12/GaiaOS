# GaiaOS — Phase 3 Engineering Design Document

**Role:** Principal Software Architect
**Status:** Phase 1 and Phase 2 complete, verified, and not reopened below — every reference to Phase 1/2 code in this document is a dependency citation, never a change request.
**Source of truth:** `docs/Architecture.md` (Architecture v1.0). This document does not alter any frozen technology decision. Where Phase 3 requires new components (a `users` table, a real task queue, a metrics layer), each one is justified against the frozen architecture's own already-stated intentions (e.g., Redis's scoped "task queue" role, §3.6's "Role-based (public/researcher/admin)" authorization model, §3.9's "reasoning-quality monitoring") — Phase 3 is *finishing* things the architecture already named, not inventing new scope.
**Deliverable type:** design only. No code. Every milestone below is written so an implementer (human or AI agent) can build it without making an architectural decision that isn't already made here.

---

## 0. What Phase 3 Is For

Phase 2 built the reasoning core — agents, orchestration, retrieval, synthesis, verification, streaming. It is functionally complete and passed engineering review. What it explicitly does not have yet, and what stands between it and "a serious open-source project" other people can depend on, run, and trust:

- No real identity — anyone can submit anything, and nothing is owned by anyone.
- No real durability — a process restart loses in-flight work, despite the infrastructure to prevent that already existing.
- No real defense against abuse — the API has no rate limits.
- An evaluation harness that exists but can't actually detect regressions yet (one benchmark question).
- A causal-reasoning feature whose data model doesn't yet support the geospatial reasoning it's named for.
- No visibility into what the system actually costs or how it actually performs in the aggregate — only per-request logs.

Phase 3 closes exactly these gaps — not new agent domains, not new reasoning capability, but the operational and trust infrastructure that turns a working reasoning engine into a system other people can rely on. This is a deliberate scope boundary, restated in §7.

---

## 1. Pre-Flight: Hidden-Dependency Analysis

Five real sequencing dependencies surfaced when tracing Phase 3's components against each other and against what Phase 1/2 already built. All five are resolved by ordering, not by adding scope.

**1. `investigations.user_id` must be added when the `users` table is added (Milestone 1), not retrofitted later.**
If Milestone 3 (durable task execution) or Milestone 8 (real ingestion) is built first and touches the `investigations` table's shape, and *then* Milestone 1 adds `user_id` afterward, every already-shipped consumer of that table (the graph nodes, the repository, the stream endpoint) needs a second pass to thread ownership through. **Resolution: Milestone 1 is first**, and every later milestone that touches `investigations` is written against the post-M1 schema from the start.

**2. Rate limiting only means something once there's an identity to limit by.**
A per-IP rate limit is a weak, easily-defeated substitute for a per-API-key/per-user quota. Building Milestone 2 (rate limiting) before Milestone 1 (auth) would mean either building IP-based limiting now and per-identity limiting later (two implementations of the same concern), or blocking on auth anyway. **Resolution: Milestone 2 depends on Milestone 1**, explicitly.

**3. A real task queue and per-investigation cost/latency metrics must not be built as two separate instrumentation passes over the same code path.**
Milestone 3 (durable task execution) rewrites *how* `run_investigation_graph` is invoked and supervised. Milestone 9 (observability) needs to instrument *that exact invocation path* to capture cost/latency/success signal. If M9 is sequenced long after M3, the implementer either instruments the old (soon-to-be-replaced) BackgroundTasks path and redoes it, or ships M3 with zero observability and has to reopen it. **Resolution: Milestone 3's own scope explicitly includes emitting the raw timing/cost/outcome events** (a small, cheap addition at the exact point where it's natural — start/end of a queued job) even though the aggregation, storage schema, and dashboard-readiness work is Milestone 9's job. This is called out explicitly in M3's spec below so it isn't missed.

**4. Real hazard-event ingestion must not be built on the wrong data model.**
`hazard_events.region` is currently a plain string (a known, accepted Phase 2 simplification). If Milestone 8 (real ingestion) is built before the schema is corrected, real historical data gets ingested into a shape that still can't do geospatial causal reasoning, and every ingested row needs re-processing once the schema is fixed. **Resolution: Milestone 7 (PostGIS geometry migration) is a hard prerequisite of Milestone 8**, sequenced immediately before it.

**5. Scheduled ingestion needs a job scheduler, and building one twice (once loosely for ingestion, once properly for durable execution) is waste.**
Architecture v1.0 already names "Celery beat / cloud scheduler" for scheduled ingestion. If Milestone 8 is built before Milestone 3 (durable task execution) exists, it either invents its own scheduling/worker mechanism or sits on cron with no shared infrastructure, retry semantics, or observability with the rest of the system. **Resolution: Milestone 8 depends on Milestone 3's worker infrastructure directly** — the same RQ/worker deployment introduced in M3 is reused, not duplicated, for scheduled ingestion jobs.

These five are reflected in the milestone ordering (§5.1) and flagged inline with **(pre-flight fix applied)** where relevant. I did not find a case requiring a redesign of anything already built in Phase 1/2 — every fix here is sequencing, matching your instruction to only redesign the roadmap if a real blocker demanded it. None did.

---

## 2. Complete Repository Structure for Phase 3

```
gaiaos/
├── auth/                              # NEW (M1) — real identity, replaces AuthStub at the seam Phase 1 built
│   ├── __init__.py
│   ├── jwt_provider.py                 # implements gateway's existing AuthProvider Protocol
│   ├── password_hashing.py             # argon2id, isolated so it's the only place a hashing library is imported
│   ├── roles.py                        # public / researcher / admin, per Architecture v1.0 §3.6
│   └── dependencies.py                 # FastAPI DI: CurrentUser, RequireRole(...)
│
├── db/models/
│   ├── user.py                         # NEW (M1)
│   ├── api_key.py                      # NEW (M2)
│   └── (investigation.py, hazard_event.py, literature_chunk.py — MODIFIED, not replaced)
│
├── gateway/
│   ├── rate_limiter_redis.py           # NEW (M2) — real RateLimiter Protocol implementation, sibling to rate_limit_stub.py
│   └── (middleware.py — MODIFIED: constructor call site swaps stubs for real providers, seam already existed)
│
├── workers/                            # NEW (M3) — mirrors app/ but for the worker process; not a subfolder of app/, deliberately, since it's a separate deployable
│   ├── __init__.py
│   ├── worker.py                       # RQ worker entrypoint
│   ├── jobs/
│   │   ├── investigation_job.py        # the queued equivalent of today's run_investigation_graph
│   │   └── ingestion_jobs.py           # NEW (M8) — scheduled hazard-event ingestion jobs
│   └── scheduler.py                    # NEW (M8) — RQ-scheduler / Celery-beat-equivalent registration
│
├── metrics/                            # NEW (M3 emits into it, M9 builds it out) — sibling to cache/, db/: a cross-cutting infra layer
│   ├── __init__.py
│   ├── events.py                       # typed metric event definitions (M3)
│   ├── collector.py                    # write path (M3, minimal) → full aggregation (M9)
│   └── aggregation.py                  # NEW (M9) — rollups, calibration feed
│
├── orchestrator/
│   ├── agents/
│   │   └── critic/
│   │       └── replan.py               # NEW (M6) — bounded replan loop, additive to the existing critic/agent.py
│   └── graph/
│       └── builder.py                  # MODIFIED (M3: queued invocation; M6: replan edge)
│
├── db/
│   └── causal_repository.py            # MODIFIED (M7): region-string equality → geometry radius query
│
├── data/migrations/versions/
│   ├── 0006_users.py                   # M1
│   ├── 0007_api_keys.py                # M2
│   ├── 0008_investigations_user_id.py  # M1
│   ├── 0009_hazard_events_geometry.py  # M7
│   └── 0010_metrics.py                 # M9
│
├── eval/
│   └── benchmarks/
│       └── questions.json              # MODIFIED (M5): 1 → real domain-covering set (data change, not structural)
│
├── ingestion/
│   └── scheduled/                      # NEW (M8), sibling to the existing one-off seed scripts
│       └── hazard_event_sources/
│           ├── usgs_historical.py
│           └── noaa_historical.py
│
├── docker-compose.yml                  # MODIFIED (M3): new `worker` service
├── Dockerfile.worker                   # NEW (M3) — see M3 for why this is a second Dockerfile, not a CMD override
│
└── docs/phase3/                        # NEW — per-milestone docs, mirrors docs/phase2/
```

**Dependency direction, extended:**
- `auth → config, db` only — never `auth → gateway` (auth *implements* gateway's `AuthProvider` Protocol; gateway must not import concrete auth internals, only the interface it already defined in Phase 1). This preserves the exact inversion-of-control seam Phase 1 built specifically for this moment.
- `workers → orchestrator, db, cache, metrics` — never `workers → app`. The worker process and the API process are two independent deployables that share the codebase's domain packages but never import each other's entrypoint code.
- `metrics → cache, db` only — no project-internal consumers depend on `metrics` except `workers` and (read-only, for dashboards) a future `app/api/v1/admin` surface — not part of Phase 3, noted in §7.
- `gateway/rate_limiter_redis.py → cache` (reuses M1-of-Phase-2's `RedisKeyBuilder` namespace already reserved for exactly this — `gaiaos:ratelimit:*` — confirmed reserved-but-unused in the Phase 2 audit).

---

## 3. Milestones

Each milestone is independently mergeable, one branch, one PR — restoring and continuing the discipline Phase 2 mostly followed.

---

### Milestone 1 — Real Authentication & Authorization

**1. Goal:** Replace `AuthStub` with a real JWT-based `AuthProvider`, add a `users` table, add `investigations.user_id`, and enforce role-based access (`public` / `researcher` / `admin`) per Architecture v1.0 §3.6.

**2. Why it exists:** Every other Phase 3 milestone (rate limiting, public API hardening, ownership on investigations) needs a real identity to attach to. This is also the single most-cited "not yet implemented" item across both prior audits.

**3. Dependencies:** none within Phase 3 — this is the root of the dependency graph (§1, point 1).

**4. Repository structure:** `auth/` (new package, §2).

**5. Files to create:** all of `auth/`, `db/models/user.py`, `data/migrations/versions/0006_users.py`, `0008_investigations_user_id.py`, `app/api/v1/auth.py` (login/register/refresh routes), `tests/test_auth.py`, `tests/test_investigation_ownership.py`.

**6. Files to modify:** `gateway/middleware.py` (constructor call site in `app/main.py`'s `create_app()` now passes a real `JWTAuthProvider` instance instead of the default `AuthStub()` — the Protocol-based seam Phase 1 built means this is a one-line change at the composition root, not a rewrite of `gateway/`), `config/settings.py` (add `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `JWT_EXPIRY_MINUTES` — validated non-empty in staging/prod via the same `model_validator` pattern already used for `DATABASE_URL`/`ENABLE_AUTH`), `app/api/v1/investigations.py` (GET/stream routes now require the requester to own the investigation or hold `admin` role — enforced via a new `RequireOwnerOrRole` dependency, not scattered inline checks).

**7. Public interfaces:**
```python
# auth/jwt_provider.py
class JWTAuthProvider:  # implements gateway.auth_stub.AuthProvider Protocol
    async def authenticate(self, request: Request) -> AuthResult: ...

# auth/roles.py
class Role(str, Enum):
    PUBLIC = "public"
    RESEARCHER = "researcher"
    ADMIN = "admin"

# auth/dependencies.py
CurrentUser = Annotated[User | None, Depends(get_current_user)]
def RequireRole(*roles: Role) -> Callable: ...
def RequireOwnerOrRole(*roles: Role) -> Callable: ...   # used by investigation GET/stream
```

**8. Internal classes:** `AuthResult` (already implied by the Phase 1 `AuthProvider` Protocol's return shape — confirmed compatible, not redefined), `UserRepository` (mirrors `InvestigationRepository`'s existing pattern — `create`, `get_by_email`, `get_by_id`; no ad hoc SQL in route handlers, consistent with the pattern established since Phase 1's `verify_extensions()`).

**9. Data flow:**
```
POST /auth/register → UserRepository.create(email, hashed_password, role=RESEARCHER default)
POST /auth/login → verify password → issue JWT (sub=user_id, role)
Every subsequent request → GatewayMiddleware → JWTAuthProvider.authenticate() → request.state.user
POST /investigations → InvestigationRepository.create(query, user_id=current_user.id)
GET /investigations/{id} → RequireOwnerOrRole(ADMIN) → 403 if requester isn't the owner and isn't admin
```

**10. Sequence (text):**
```
Client -> API: POST /auth/login {email, password}
API -> UserRepository: get_by_email(email)
API -> password_hashing: verify(password, user.hashed_password)
alt valid
  API -> jwt_provider: issue_token(user)
  API -> Client: 200 {access_token}
else invalid
  API -> Client: 401 {error_code: "invalid_credentials"}
end

Client -> API: GET /investigations/{id}  [Authorization: Bearer <token>]
API -> GatewayMiddleware: authenticate(request)
GatewayMiddleware -> JWTAuthProvider: authenticate(request)
JWTAuthProvider -> API: AuthResult(user_id, role)
API -> RequireOwnerOrRole: check(investigation.user_id, current_user)
alt owner or admin
  API -> Client: 200 {investigation}
else
  API -> Client: 403 {error_code: "not_authorized"}
end
```

**11. Error handling:** invalid/expired JWT → `401` with `error_code: "invalid_token"`, never a stack trace (same pattern as every other error response since Phase 1's `/health/ready`). Ownership mismatch → `403`, not `404` — deliberately: a `404` on an existing-but-not-owned resource is a form of information leakage debate that goes either way in security literature; this design chooses `403` because GaiaOS investigation IDs are UUIDs (not enumerable/guessable), so confirming existence-but-denying-access doesn't meaningfully leak anything a UUID-guessing attacker didn't already have to get right anyway, and `403` gives legitimate users a clearer error than an ambiguous `404`. Password hashing failures (e.g., a corrupted stored hash) → `500`, logged with full detail server-side, generic message to client.

**12. Logging requirements:** login success/failure logged with `user_id` (on success) or `email_attempted` (on failure, **never** the password) — structured, consistent with the existing "never log secrets" discipline verified clean in both prior audits.

**13. Testing strategy:** Unit — password hashing round-trip, JWT issue/verify/expiry. Integration — full register → login → authenticated request flow. Failure-path — expired token, tampered token (signature mismatch), wrong password, non-owner accessing another user's investigation. Edge case — first-ever registered user (should this be auto-admin? **Decision: no** — admin role is granted out-of-band by an existing admin or a seed script, never by "first user wins," which is a common privilege-escalation footgun in bootstrap flows).

**14. CI impact:** none structurally new — extends the existing real-Postgres-in-CI pattern.

**15. Documentation impact:** `docs/phase3/authentication.md` — token lifecycle, role model, and explicitly documents the "no auto-admin" bootstrap decision so it isn't reinvented differently later.

**16. Definition of Done:** a user can register, log in, submit an investigation, retrieve only their own investigations (403 on others'), and an admin-role user can retrieve any investigation.

**17. Risks:** JWT secret rotation isn't designed here (out of scope — noted explicitly in §7) — acceptable for Phase 3's actual need (a single, stable signing key), not acceptable indefinitely, flagged as future work, not silently ignored.

**18. Future extensibility:** `Role` enum and `RequireRole` are deliberately generic — Milestone 10 (public API hardening) reuses them for API-key-scoped access without modification.

---

### Milestone 2 — Real Rate Limiting

**1. Goal:** Replace `RateLimitStub` with a Redis-backed token-bucket limiter, scoped per-user (authenticated) and per-IP (unauthenticated), plus API-key-scoped limits for Milestone 10's external consumers.

**2. Why it exists:** the API currently has no defense against submission flooding — directly relevant now that Milestone 3 makes each submission durable and worker-consumed (a flood of submissions becomes a flood of queued work, not just wasted HTTP cycles).

**3. Dependencies:** Milestone 1 (§1, point 2).

**4. Repository structure:** `gateway/rate_limiter_redis.py` only.

**5. Files to create:** `gateway/rate_limiter_redis.py`, `tests/test_rate_limiter.py`.

**6. Files to modify:** `app/main.py` composition root (swap `RateLimitStub()` for `RedisRateLimiter(redis_client)`), `config/settings.py` (`RATE_LIMIT_REQUESTS_PER_MINUTE`, per-role overrides).

**7. Public interfaces:**
```python
class RedisRateLimiter:  # implements gateway.rate_limit_stub.RateLimiter Protocol
    async def check(self, identity: str, scope: str) -> RateLimitResult: ...
```

**8. Internal classes:** `RateLimitResult(allowed: bool, retry_after_seconds: int | None)`. Token-bucket state stored under `RedisKeyBuilder.rate_limit_key(identity, scope)` — reusing the namespace explicitly reserved for this since Phase 2's Milestone 1.

**9. Data flow:** `GatewayMiddleware → RedisRateLimiter.check(identity, scope) → Redis (atomic INCR + TTL via a Lua script or pipelined transaction, not read-then-write, to avoid a race under concurrent requests) → allow/deny`.

**10. Sequence (text):**
```
Client -> API: POST /investigations
GatewayMiddleware -> RedisRateLimiter: check(user_id or client_ip, scope="submit")
RedisRateLimiter -> Redis: EVALSHA <token_bucket_script> [key] [capacity] [refill_rate]
Redis -> RedisRateLimiter: {allowed, remaining, retry_after}
alt allowed
  GatewayMiddleware -> next handler
else denied
  GatewayMiddleware -> Client: 429 {error_code: "rate_limited", retry_after}
end
```

**11. Error handling:** Redis unreachable at check-time → **fail open, not closed**, explicitly — a rate limiter that blocks all traffic when its own backend is down turns an availability problem into a worse one; this is a deliberate, documented trade (different from Milestone 1's checkpointer, which fails closed, because losing an in-flight investigation is worse than briefly having no rate limit — the asymmetry is intentional and stated).

**12. Logging requirements:** denials logged with `identity`, `scope`, `current_count` — feeds abuse-pattern detection later (not built in Phase 3, but the log shape should support it without rework).

**13. Testing strategy:** Unit — token-bucket math (refill rate, burst capacity) against a fake clock. Integration — real Redis, concurrent requests correctly rate-limited (a race-condition test specifically, given the atomic-script requirement in §9). Failure-path — Redis down → asserts fail-open. Edge case — role-based override (researcher gets a higher quota than public) correctly applied.

**14. CI impact:** none new.

**15. Documentation impact:** `docs/phase3/rate_limiting.md` — documents the fail-open decision explicitly, since it's the kind of choice a future security reviewer will (correctly) want justified in writing, not just found in code.

**16. Definition of Done:** submission flooding from a single identity is throttled with a correct `429`/`Retry-After`, verified under concurrent load in a test, with Redis-down fail-open behavior proven, not assumed.

**17. Risks:** token-bucket parameter tuning (capacity/refill rate) is a product decision more than an engineering one — ship with conservative defaults, documented as tunable via `Settings`, not hardcoded.

**18. Future extensibility:** the `scope` parameter (`"submit"`, `"stream"`, etc.) means Milestone 10 can add new scopes (e.g., `"api_key_burst"`) without touching the limiter's core logic.

---

### Milestone 3 — Durable Task Execution (Redis-Backed Queue)

**1. Goal:** Replace FastAPI `BackgroundTasks` with RQ (Redis Queue — chosen specifically because Architecture v1.0 names "RQ/Celery" and RQ is the simpler of the two for a single-queue, no-multi-broker use case, consistent with the project's repeated preference for the simplest tool that satisfies the actual requirement), running as a separate `worker` process/service, so investigations survive an API-process restart and gain real retry semantics.

**2. Why it exists:** this is the single highest-severity durability gap identified across both prior audits — the checkpointer infrastructure to make investigations resumable already exists and is unused for that purpose today.

**3. Dependencies:** Milestone 1 (`investigations.user_id` must exist before job records are created against the final schema shape, §1 point 1).

**4. Repository structure:** `workers/` (new top-level package, §2), `Dockerfile.worker` (new).

**5. Files to create:** `workers/__init__.py`, `workers/worker.py`, `workers/jobs/investigation_job.py`, `Dockerfile.worker`, `metrics/__init__.py`, `metrics/events.py`, `metrics/collector.py` (minimal write-path only — full aggregation is M9), `tests/test_investigation_job.py`, `tests/test_worker_retry.py`.

**6. Files to modify:** `app/api/v1/investigations.py` (`POST /investigations` now enqueues via RQ instead of `background_tasks.add_task`), `orchestrator/graph/builder.py` (the graph invocation entrypoint moves from being called directly by the API process to being called by `workers/jobs/investigation_job.py`; no change to the graph's internal logic, only to *what calls it*), `docker-compose.yml` (new `worker` service, built from `Dockerfile.worker`, sharing the same Redis/Postgres dependencies as `app`).

**Why a second Dockerfile, not a CMD override on the same image:** the `worker` process doesn't need `app/api/*` route code or the Gateway middleware stack, and the `app` process doesn't need `workers/jobs/*`. Two thin Dockerfiles sharing the same base layers (both `COPY` the same core packages — `orchestrator/`, `db/`, `cache/`, `config/`, `metrics/` — but diverge on the final `COPY`/`CMD`) keeps each image's actual runtime surface honest, and — directly addressing the Critical finding from the Phase 2 audit — **this milestone's Definition of Done explicitly requires both images to be built and smoke-tested in CI**, closing the exact CI gap that let the Phase 2 Dockerfile bug ship undetected. This is not optional scope creep; it is the direct, named fix for that finding, done here because this is the first milestone that changes the Docker build surface since that finding was raised.

**7. Public interfaces:**
```python
# workers/jobs/investigation_job.py
def run_investigation_job(investigation_id: UUID) -> None: ...   # RQ entrypoint, sync wrapper around the existing async graph invocation

# app/api/v1/investigations.py
# POST /investigations now does:
queue.enqueue(run_investigation_job, investigation.id, job_timeout="10m", retry=Retry(max=2))
```

**8. Internal classes:** none new beyond the job wrapper — deliberately thin, since the graph/agent logic itself is unchanged; only its invocation site moves.

**9. Data flow:**
```
POST /investigations → InvestigationRepository.create(user_id, query) [status='planning']
  → RQ.enqueue(run_investigation_job, investigation_id)
  → 202 {investigation_id, poll_url, stream_url}   [response returns before the job runs, same external contract as before]

[separate worker process, polling the queue]
run_investigation_job(investigation_id)
  → metrics.collector.emit(JobStarted(investigation_id, enqueued_at, started_at))
  → graph.ainvoke(...) [unchanged from Phase 2]
  → metrics.collector.emit(JobCompleted(investigation_id, status, duration, llm_cost_estimate))
```

**10. Sequence (text):**
```
Client -> API: POST /investigations
API -> InvestigationRepository: create()
API -> RQ (Redis): enqueue(run_investigation_job, id)
API -> Client: 202 {investigation_id, ...}

Worker -> RQ (Redis): dequeue
Worker -> investigation_job: run_investigation_job(id)
investigation_job -> metrics: emit(JobStarted)
investigation_job -> Graph: ainvoke(state, thread_id=id)
Graph -> [same M2-M9 Phase 2 flow, unchanged]
investigation_job -> metrics: emit(JobCompleted)

alt worker crashes mid-job
  RQ -> RQ: job requeued per Retry(max=2) policy
  Worker (new instance, or restarted) -> RQ: dequeue same job
  investigation_job -> Graph: ainvoke(state, thread_id=id)  [LangGraph checkpointer resumes from last checkpoint, not from scratch]
end
```

**11. Error handling:** job exceptions caught at the `investigation_job` boundary → `InvestigationRepository.update_status('failed', ...)`, same terminal-state guarantee Phase 2 already established, just now reachable from a retried context too. RQ's own `Retry(max=2)` policy handles transient worker crashes; after exhausting retries, the investigation is marked `failed` with a specific `error_code: "job_retries_exhausted"` rather than left in `planning` forever — this directly closes the durability gap identified in the Phase 2 audit.

**12. Logging requirements:** job enqueue/dequeue/start/complete/retry all logged with `investigation_id`, `job_id`, `attempt_number` — this is also the exact event set `metrics/events.py` defines, so logging and metrics share a single source of truth rather than being two parallel, potentially-drifting instrumentation paths.

**13. Testing strategy:** Unit — `investigation_job`'s sync/async bridging. Integration — real RQ + real Redis, full submit → worker picks up → complete flow. Failure-path — **simulated worker crash mid-job** (kill the worker process between two checkpoints, start a new worker, assert the investigation still reaches `complete` via checkpoint resume, not from scratch) — this is the single most important test in this milestone, since it's the direct verification of the durability property the whole milestone exists for. Edge case — job retries exhausted → asserts `status='failed'` with the specific error code, never stuck.

**14. CI impact:** CI now builds **both** `app` and `worker` images and smoke-tests both starting successfully — the direct fix for the Phase 2 Dockerfile gap, scoped here per point 6 above.

**15. Documentation impact:** `docs/phase3/task_execution.md` — documents why RQ over Celery (simplicity, single-queue sufficiency, matching the project's own stated preference for the simplest adequate tool — the same reasoning Architecture v1.0 already applied to reject Kafka), and the worker deployment topology.

**16. Definition of Done:** a worker-crash-mid-investigation test passes, demonstrating actual checkpoint-based resume (not just "the code compiles and doesn't obviously break"); both `app` and `worker` Docker images build and smoke-test green in CI.

**17. Risks:** this is the largest-blast-radius milestone in Phase 3 — it changes the execution model of every investigation in the system. Recommend feature-flagging the switch (`Settings.USE_QUEUED_EXECUTION`, defaulting to the new path once tested, with the old `BackgroundTasks` path retained-but-deprecated for exactly one milestone's worth of rollback safety, then removed in a follow-up cleanup — not indefinitely, to avoid two permanent execution paths).

**18. Future extensibility:** Milestone 8's scheduled ingestion jobs are registered on this exact same RQ/worker infrastructure, not a second job system.

---

### Milestone 4 — Redis Hardening (Persistence + Checkpoint TTL)

**1. Goal:** Add AOF persistence to the Redis deployment and a TTL/eviction policy for LangGraph checkpoint keys, closing the two Redis operational gaps identified in the Phase 2 audit.

**2. Why it exists:** Milestone 3 makes checkpoint-based resume a real, tested, load-bearing property. That property is worthless if Redis itself loses data on restart (no persistence) or grows unbounded (no TTL) — this milestone is the direct completion of M3's durability story, deliberately sequenced right after it.

**3. Dependencies:** Milestone 3 (must exist first — hardening a mechanism that didn't matter yet would be premature).

**4. Repository structure:** no new packages — this is a configuration and a small code change to `orchestrator/graph/checkpointer.py`.

**5. Files to create:** `tests/test_checkpoint_ttl.py`.

**6. Files to modify:** `docker-compose.yml` (Redis service: `command: redis-server --appendonly yes`, new named volume `redis_data`), `orchestrator/graph/checkpointer.py` (add `ex=<ttl_seconds>` to every checkpoint write, TTL sourced from `Settings.CHECKPOINT_TTL_SECONDS`, default generous enough to cover the `job_timeout` + `Retry(max=2)` worst case from M3 with margin — computed explicitly, not guessed, e.g. `job_timeout * (max_retries + 1) * safety_factor`).

**7. Public interfaces:** no new public interface — `RedisCheckpointSaver`'s existing `aput`/`aget_tuple` signatures are unchanged, only their internal Redis calls gain a TTL argument.

**8. Internal classes:** none new.

**9. Data flow:** unchanged from M3's checkpointer flow — the only difference is every write now carries an expiry, and a background reaper is unnecessary since Redis's own TTL mechanism handles eviction natively (no new component needed for this).

**10. Sequence (text):** N/A — no new sequence, this milestone modifies existing write calls' parameters, not the flow itself.

**11. Error handling:** none new — TTL expiry of a checkpoint for a *completed* investigation is expected and harmless (the durable record of the investigation is in Postgres, per Phase 2's `investigations` table; the Redis checkpoint's only job was enabling mid-run resume, and has no reason to exist after completion). TTL expiry of a checkpoint for a still-*running* investigation would be a bug in the TTL-sizing calculation — explicitly tested (point 13).

**12. Logging requirements:** none new.

**13. Testing strategy:** Unit — TTL calculation formula. Integration — real Redis, assert a checkpoint key actually expires after its TTL via `redis-cli TTL`/direct client check. Failure-path/edge case — a deliberately-short TTL in a test config, combined with a deliberately-slow fake agent, proving the TTL is sized correctly relative to worst-case job duration (this is the test that actually validates the sizing formula, not just that TTL-setting code runs).

**14. CI impact:** Redis service in `docker-compose.yml`/CI now needs a persistent volume mount even in CI's ephemeral environment — trivial, but worth noting since CI's Redis previously had no volume at all.

**15. Documentation impact:** `docs/phase3/redis_operations.md` — the TTL sizing formula, explicitly, so a future change to `job_timeout` or `max_retries` in M3's config has a documented place to also revisit this TTL.

**16. Definition of Done:** Redis data survives a container restart (AOF verified via an integration test that restarts the Redis container mid-test and confirms data presence); checkpoint keys correctly expire on the documented schedule and never expire mid-run under the worst-case timing this milestone calculated.

**17. Risks:** AOF persistence has a real disk-I/O cost — acceptable at Phase 3's scale, worth a one-line note in the docs that this is a production-scale-dependent tuning knob (`appendfsync everysec` vs `always`), not re-litigated here since it doesn't block anything.

**18. Future extensibility:** none needed — this milestone closes a gap, it doesn't open new surface.

---

### Milestone 5 — Evaluation Harness Expansion + CI Regression Gate

**1. Goal:** Expand the benchmark question set from one question to real, domain-covering coverage, and wire the eval harness into CI as an actual regression gate (not just a mechanism that exists but is never exercised meaningfully).

**2. Why it exists:** this is Architecture v1.0's own explicitly stated regret ("build the eval harness first") finally being made real, and it's the direct, named prerequisite for Milestone 6 (bounded replan loop), which was deliberately deferred pending exactly this.

**3. Dependencies:** none new beyond what already exists (Phase 2's M1 eval harness mechanics) — this is a data-and-CI-wiring milestone, not a new system.

**4. Repository structure:** no new packages — `eval/benchmarks/questions.json` grows, `eval/harness/` gains a CI-invocable entrypoint if one doesn't already cleanly exist.

**5. Files to create:** `eval/benchmarks/questions.json` gains ~15–20 new entries (one per domain: air_quality, seismic, ocean, atmosphere, wildfire, literature, causal_chain, simulation-triggering; at least one multi-domain moderate query; at least one deliberately-unanswerable query verifying the "unable to gather evidence" path stays honest — directly testing the M7/Phase-2-audit-flagged CitationMapper/evidence-gap behavior with real signal for the first time), `eval/harness/ci_gate.py` (thin CLI entrypoint: run suite, compare score against the previous recorded run for the same benchmark set, exit non-zero on regression beyond a documented threshold), `tests/test_eval_ci_gate.py`.

**6. Files to modify:** `.github/workflows/ci.yml` (new job or step: run the eval suite — **on a schedule/nightly, not on every PR**, explicitly reasoned in point 11 below), `config/settings.py` (`ORCHESTRATOR_VERSION` — confirmed already present from Phase 2's eval design, verify it's actually being set from CI's git SHA rather than a static default, closing a gap if it wasn't).

**7. Public interfaces:**
```python
# eval/harness/ci_gate.py
def check_for_regression(current_run: BenchmarkSuiteResult, baseline: BenchmarkSuiteResult, threshold: float) -> RegressionReport: ...
```

**8. Internal classes:** `RegressionReport(regressed: bool, per_question_deltas: list[...], summary: str)`.

**9. Data flow:**
```
CI (nightly) → run_benchmark_suite(orchestrator_version=git_sha)
  → for each of ~20 questions: submit real investigation via the queued-execution path from M3 → poll to completion → score
  → INSERT eval_benchmark_runs (per M1's existing table)
  → fetch the most recent prior run for comparison
  → check_for_regression(current, baseline, threshold)
  → if regressed: CI job fails, posts a summary (which questions regressed, by how much)
```

**10. Sequence (text):**
```
Scheduler -> CI: nightly trigger
CI -> eval/harness/runner: run_benchmark_suite(version)
loop for each benchmark question
  runner -> API (queued path): submit investigation
  runner -> API: poll until complete
  runner -> scorer: score(question, result)
end
runner -> Postgres: INSERT eval_benchmark_runs
runner -> Postgres: SELECT most recent prior run
runner -> ci_gate: check_for_regression(current, baseline, threshold)
alt regression found
  CI -> GitHub: fail job, post summary
else
  CI -> GitHub: pass
end
```

**11. Error handling / why nightly, not per-PR:** running ~20 real (LLM-calling, external-API-calling) investigations on every PR would be slow, costly, and flaky in a way that would train the team to ignore CI failures — a well-known failure mode for expensive test suites. **Decision: nightly scheduled run, with results visible in a dashboard-readable table (M9 builds the dashboard; this milestone only guarantees the data exists and CI fails loudly on regression), plus a manually-triggerable `workflow_dispatch` for on-demand runs before a risky merge.** This is a considered trade-off, not a shortcut — stated explicitly so it isn't mistaken for scope-cutting.

**12. Logging requirements:** each benchmark question's run logged with `question_id`, `score`, `duration_ms`, `orchestrator_version` — already the shape M1 established in Phase 2, no new logging design needed, just real volume flowing through it for the first time.

**13. Testing strategy:** Unit — `check_for_regression`'s threshold math against fixture score pairs. Integration — the full nightly-gate flow against a small (3-question) test fixture set, run synchronously in the test itself rather than waiting for a real nightly schedule. Failure-path — a deliberately-regressed fixture result correctly fails the gate. Edge case — first-ever run (no baseline to compare against) → passes trivially, doesn't crash on a missing prior row.

**14. CI impact:** new scheduled workflow, separate from the existing per-PR `ci.yml` job — explicitly not blocking normal PR velocity.

**15. Documentation impact:** `docs/phase3/evaluation.md` — the full ~20-question set's rationale (why these specific questions cover what they cover), and the nightly-vs-per-PR trade-off reasoning from point 11.

**16. Definition of Done:** the nightly gate runs against a real, domain-covering benchmark set and demonstrably fails when a deliberately-introduced regression fixture is fed through it in a test — this is the concrete proof the gate works, not just that it exists.

**17. Risks:** benchmark question quality (are the reference answers actually correct, are the domains actually covered well) is a content-curation risk, not an engineering one — flagged as needing the same care a test suite's assertions need, not treated as a solved problem just because the mechanism exists.

**18. Future extensibility:** `RegressionReport`'s per-question deltas are structured data, directly consumable by M9's dashboard without rework.

---

### Milestone 6 — Bounded Critic Replan Loop

**1. Goal:** Implement the capped (max 2 cycles) replan loop that Architecture v1.0 explicitly deferred pending real eval signal — now unblocked by Milestone 5.

**2. Why it exists:** this is a named, intentional deferral from the frozen architecture being picked back up at exactly the point it was designed to be picked up — not new scope invented in Phase 3, but scope that was always planned, gated correctly.

**3. Dependencies:** Milestone 5 (hard dependency, explicitly, per the frozen architecture's own prior decision — this milestone cannot start without a real benchmark baseline to measure "does replanning actually help" against, and skipping that measurement would repeat the exact mistake Architecture v1.0's own retrospective called out).

**4. Repository structure:** `orchestrator/agents/critic/replan.py` (new, additive to the existing `critic/agent.py`).

**5. Files to create:** `orchestrator/agents/critic/replan.py`, `tests/test_replan_loop.py`.

**6. Files to modify:** `orchestrator/graph/builder.py` (new conditional edge: Critic → replan trigger → back to the relevant domain agent(s), capped), `orchestrator/schemas/graph_state.py` (add `replan_count: int` to `TaskGraphState`, defaulting to 0).

**7. Public interfaces:**
```python
def should_replan(critic_flags: list[CriticFlag], replan_count: int, max_replans: int = 2) -> bool: ...
def build_replan_targets(critic_flags: list[CriticFlag]) -> list[str]:  # which domains to re-query, not all of them
    ...
```

**8. Internal classes:** none new beyond the two functions above — deliberately thin, following M2's own precedent (small logic inserted into an existing graph seam, not new plumbing).

**9. Data flow:**
```
Critic.verify(synthesis) → CriticFlag[]
should_replan(flags, state.replan_count, max=2)?
  if yes: build_replan_targets(flags) → re-invoke only those domain agents → increment replan_count → back to Synthesis
  if no (either no high-severity flags, or replan_count == max): proceed to terminal node
```

**10. Sequence (text):**
```
Graph -> Critic: verify(synthesis)
Critic -> Graph: CriticFlag[]
Graph -> should_replan: check(flags, replan_count=0, max=2)
alt high-severity flag AND replan_count < max
  Graph -> build_replan_targets: (flags) -> ["seismic"]
  Graph -> SeismicAgent: run(input)  [targeted re-query, not full fan-out]
  Graph -> Synthesis: synthesize(updated evidence)
  Graph -> Critic: verify(new synthesis)
  Graph -> should_replan: check(flags, replan_count=1, max=2)
  ... [capped at 2 total cycles]
else
  Graph -> Terminal: finalize
end
```

**11. Error handling:** if the replan cap is hit while flags still indicate unresolved conflicts, the frozen architecture's own explicit requirement applies unchanged: the final answer must state "unresolved conflicting evidence" rather than silently picking a side — this milestone implements that exact requirement, which was already specified in Architecture v1.0 §3.10 and simply hadn't been reachable code until now.

**12. Logging requirements:** each replan cycle logged with `investigation_id`, `cycle_number`, `targeted_domains`, `trigger_reason` (which flag caused it) — this is itself new, valuable explainability content, feeding directly into the SSE `critic_flag` event stream already built in Phase 2 (a `replanning` event type is a natural, small addition to that existing catalog).

**13. Testing strategy:** Unit — `should_replan`/`build_replan_targets` logic against fixture flag sets. Integration — full graph run where a deliberately-conflicting evidence fixture triggers exactly one replan cycle and resolves. Failure-path — flags that never resolve even after 2 cycles → asserts the "unresolved conflicting evidence" terminal message, never an infinite loop (this is the same class of risk M6-of-Phase-2's cycle-safety test protected against in the causal-chain CTE — same discipline, different subsystem). Edge case — `replan_count` cap exactly at the boundary (cycle 2 triggers, cycle 3 must not).

**14. CI impact:** the new benchmark questions from M5 should include at least one designed specifically to exercise this loop (a query with genuinely conflicting evidence sources) — noting this as a cross-milestone content dependency, not a code dependency.

**15. Documentation impact:** `docs/phase3/replan_loop.md`, directly citing the eval-driven decision to build this now (M5's baseline vs. post-replan-loop comparison run) as the actual evidence that this feature is worth its added cost/latency — closing the loop on Architecture v1.0's own stated concern about whether this feature would actually help.

**16. Definition of Done:** a controlled A/B comparison (replan loop on vs. off) against the M5 benchmark set, with the result — whether it measurably improves the calibration/accuracy metrics — documented, not assumed. If the measured result is "no meaningful improvement," that is a valid, acceptable Definition-of-Done outcome too (ship it disabled by a feature flag, documented as evaluated-and-deferred) — this milestone's job is to produce the *measurement*, not to guarantee a positive result.

**17. Risks:** added latency/cost per investigation for queries that trigger replanning — directly the cost/latency trade-off the original architecture review flagged; mitigated by capping at 2 cycles and only targeting the specific flagged domains, not a full re-fan-out.

**18. Future extensibility:** `replan_count` in `TaskGraphState` is generic enough to support a future, more sophisticated replan strategy (e.g., varying the cap by complexity tier) without a schema change.

---

### Milestone 7 — PostGIS Geometry Migration for Hazard Events

**1. Goal:** Migrate `hazard_events.region` from a plain string to a real `GEOMETRY(Point, 4326)` column with a GIST index, and update the causal-chain query to use radius-based proximity matching instead of exact-string equality.

**2. Why it exists:** this is the direct, named fix for the Phase 2 audit's highest architecture-consistency finding — PostGIS exists in this system specifically to justify this table's geospatial reasoning, and today it doesn't use it.

**3. Dependencies:** none within Phase 3 beyond ordinary sequencing — deliberately placed immediately before Milestone 8 (§1, point 4) so real data is never ingested into the old shape.

**4. Repository structure:** no new packages — `db/models/hazard_event.py` and `db/causal_repository.py` are modified in place.

**5. Files to create:** `data/migrations/versions/0009_hazard_events_geometry.py`, `tests/test_geospatial_causal_query.py`.

**6. Files to modify:** `db/models/hazard_event.py` (`region: Mapped[str]` → `region: Mapped[Geometry]`, plus a new `region_label: str | None` column retained for human-readable display — the string isn't discarded, it's demoted from "the only representation" to "a display label alongside the real geometry"), `db/causal_repository.py` (the recursive CTE's `he.region = :region` becomes `ST_DWithin(he.region, :point, :radius_meters)`), `orchestrator/agents/causal_chain/agent.py` (now resolves a region *name* to coordinates via the same geocoding tool Phase 2 already built for other agents — no new geocoding code, reuse of an existing, already-hardened-per-the-Phase-2-audit component).

**7. Public interfaces:**
```python
async def find_causal_chain(event_type: str, point: tuple[float, float], radius_meters: float, max_depth: int = 4) -> list[Evidence]: ...
```
(signature change from Phase 2's `region: str` to `point: tuple[float, float], radius_meters: float` — a breaking internal-interface change, acceptable because this function has exactly one caller, the Causal Chain agent, which is modified in the same milestone.)

**8. Internal classes:** none new.

**9. Data flow:**
```
CausalChainAgent.run(input)
  → resolve region name to (lat, lon) via existing geocoding tool
  → find_causal_chain(event_type, point, radius_meters=default_from_settings, max_depth=4)
  → recursive CTE now filters on ST_DWithin at each hop, not string equality
  → Evidence[] as before
```

**10. Sequence (text):**
```
FanOutCoordinator -> CausalChainAgent: run(input)
CausalChainAgent -> Geocoding Tool: resolve(region_name)
Geocoding Tool -> CausalChainAgent: (lat, lon)  [or explicit gap, per the already-fixed Phase 2 fallback behavior]
CausalChainAgent -> Postgres: WITH RECURSIVE chain AS (... ST_DWithin(region, point, radius) ...)
Postgres -> CausalChainAgent: rows
CausalChainAgent -> Graph: AgentOutput(evidence=[...])
```

**11. Error handling:** geocoding failure → the causal chain agent surfaces an explicit gap (`errors=["could not resolve region for causal analysis"]`) exactly like every other agent's tool-failure path — no new error-handling pattern invented, reuse of the established one.

**12. Logging requirements:** log the resolved `radius_meters` and hop count per query — useful for later tuning the default radius, which is a product/domain judgment call, not something to over-engineer now.

**13. Testing strategy:** Unit — `ST_DWithin` query construction. Integration — seeded fixture events at known coordinates (e.g., two points 5km apart, one 500km apart), asserting the radius query correctly includes the near pair and excludes the far one — this is the concrete test that proves the migration actually delivers the geospatial reasoning capability the whole system claims to have. Failure-path — geocoding failure → explicit gap, not a crash. Edge case — migrating existing seeded fixture data (Phase 2's `ingestion/hazard_event_seed.py` rows, all currently `region="Tokyo"` strings) — the migration must backfill real coordinates for existing rows, not just accept new ones in the new shape; a data-migration step (not just a schema migration) is part of this milestone's scope.

**14. CI impact:** none structurally new.

**15. Documentation impact:** `docs/phase3/geospatial_causal_reasoning.md` — the default radius value and its rationale, and an explicit note that this migration directly closes a named finding from the Phase 2 audit, so the history is traceable for anyone reading the repo later.

**16. Definition of Done:** the near/far radius test in point 13 passes; all pre-existing seeded fixture rows are correctly backfilled with real coordinates, not left null or dropped.

**17. Risks:** default radius tuning is a genuine domain-judgment risk (too small misses real correlations, too large returns noise) — ship with a documented, conservative default and make it `Settings`-configurable, not hardcoded, so it can be tuned without a redeploy-requiring code change.

**18. Future extensibility:** `ST_DWithin` is the simplest correct PostGIS proximity predicate for this use case — if future needs require polygon-overlap (fire perimeters, flood extents, per Architecture v1.0's own original PostGIS justification), the `region` column is already the right geometry type to support that without a further migration, only a query change.

---

### Milestone 8 — Real Hazard-Event Ingestion Pipeline

**1. Goal:** Replace the hand-written fixture seed script with scheduled, automated ingestion of real historical hazard data (starting with USGS and NOAA, the two sources already integrated as live tool/MCP clients in Phase 2), populating `hazard_events`/`hazard_relationships` on an ongoing basis.

**2. Why it exists:** the Causal Chain agent's real value is proportional to the data behind it — Phase 2's fixture seed data was always explicitly scoped as a Phase 3+ concern once the schema was ready (§1 point 4) and the worker infrastructure existed to schedule it properly (§1 point 5) — both are now true.

**3. Dependencies:** Milestone 7 (schema must be correct first), Milestone 3 (worker/scheduler infrastructure).

**4. Repository structure:** `ingestion/scheduled/` (new, §2), `workers/scheduler.py` (new, §2).

**5. Files to create:** `ingestion/scheduled/hazard_event_sources/{usgs_historical,noaa_historical}.py`, `workers/scheduler.py`, `workers/jobs/ingestion_jobs.py`, `tests/test_ingestion_jobs.py`, `tests/test_usgs_historical_source.py`, `tests/test_noaa_historical_source.py`.

**6. Files to modify:** `docker-compose.yml` (a scheduler process — RQ-scheduler, run as a third lightweight service alongside `app`/`worker`, or a cron-triggered enqueue if the team prefers not to run a persistent scheduler process; **decision: RQ-scheduler as a service**, consistent with keeping all queued/scheduled logic on one mechanism rather than mixing in host cron, which doesn't survive container restarts as cleanly), `config/settings.py` (`INGESTION_POLL_INTERVAL_HOURS`, per-source enable/disable flags).

**7. Public interfaces:**
```python
async def fetch_recent_usgs_events(since: datetime) -> list[HazardEventRecord]: ...
async def fetch_recent_noaa_events(since: datetime) -> list[HazardEventRecord]: ...

def run_ingestion_job(source: str) -> None: ...   # RQ job entrypoint, per source
```

**8. Internal classes:** `HazardEventRecord` (the ingestion-layer shape, mapped to the `hazard_events` ORM model by a thin adapter — kept distinct from the ORM model itself so a source's raw shape doesn't leak into the DB layer's contract), `IngestionCursor` (tracks `last_ingested_at` per source in a small dedicated table, so each scheduled run only fetches genuinely new data, not a full re-pull every time).

**9. Data flow:**
```
Scheduler (hourly, per Settings) → enqueue run_ingestion_job("usgs")
Worker → run_ingestion_job("usgs")
  → IngestionCursor.get_last_run("usgs")
  → fetch_recent_usgs_events(since=last_run)
  → deduplicate against existing hazard_events (by source + external_id, a new column added to support exactly this)
  → INSERT new hazard_events rows
  → IngestionCursor.update_last_run("usgs", now())
  → metrics.collector.emit(IngestionCompleted(source, records_ingested, duration))
```

**10. Sequence (text):**
```
RQ-Scheduler -> Redis: trigger (per configured interval)
Worker -> ingestion_jobs: run_ingestion_job("usgs")
ingestion_jobs -> IngestionCursor: get_last_run("usgs")
ingestion_jobs -> usgs_historical: fetch_recent_usgs_events(since)
usgs_historical -> USGS API: fetch
USGS API -> usgs_historical: raw events
ingestion_jobs -> Postgres: dedupe check (source, external_id)
ingestion_jobs -> Postgres: INSERT new hazard_events
ingestion_jobs -> IngestionCursor: update_last_run("usgs", now())
ingestion_jobs -> metrics: emit(IngestionCompleted)
```

**11. Error handling:** a failed ingestion run for one source doesn't affect the cursor (cursor only advances on success), so the next scheduled run retries from the same `since` point — no data loss on a transient failure, no manual intervention needed for typical transient errors. Persistent failures (source API genuinely down/changed) surface via the same structured logging → operator visibility, not a silent no-op.

**12. Logging requirements:** every ingestion run logged with `source`, `records_fetched`, `records_inserted` (post-dedup), `duration_ms` — directly feeds M9's dashboard.

**13. Testing strategy:** Unit — deduplication logic against fixture data with intentional overlaps. Integration — mocked USGS/NOAA HTTP responses (same `respx` pattern established in Phase 2, reused, not reinvented) driving a full ingestion job run, asserting correct inserts and cursor advancement. Failure-path — source API failure → asserts cursor doesn't advance, next run retries the same window. Edge case — a record with a duplicate `external_id` from a prior run → correctly skipped, not double-inserted.

**14. CI impact:** the new `scheduler` service needs to be part of the CI smoke-test matrix established in M3 — extending, not duplicating, that pattern.

**15. Documentation impact:** `docs/phase3/hazard_ingestion.md` — per-source field mapping (raw USGS/NOAA shape → `HazardEventRecord`), explicitly documented since this is exactly the kind of mapping that silently drifts if a source changes its API shape and isn't caught by anything except a human who knows what changed.

**16. Definition of Done:** a real (not mocked, run manually once against live USGS/NOAA endpoints as part of milestone verification, though CI itself stays mocked per point 13) ingestion run populates `hazard_events` with genuine historical data, correctly deduplicated on a second run.

**17. Risks:** external API shape drift over time — mitigated by the dedicated field-mapping documentation (point 15) and by the existing `respx`-mocked test suite catching any local code assumption breaking, though it can't catch the live API itself changing shape (a monitoring concern, not a testing one — noted, not solved, in this milestone).

**18. Future extensibility:** adding a third source (FIRMS wildfire, already integrated as a live tool client in Phase 2) is a drop-in addition following the exact same `fetch_recent_X_events` + `run_ingestion_job(source)` pattern — explicitly not built in this milestone (scope discipline — two sources prove the pattern, a third is trivial follow-on work, not designed speculatively here).

---

### Milestone 9 — Observability & Cost/Latency Metrics

**1. Goal:** Build out the aggregation, storage, and query-ability of the metric events Milestone 3 started emitting (job timing) and Milestone 8 extended (ingestion timing) — turning raw events into the "reasoning-quality monitoring" Architecture v1.0 §3.9 explicitly calls for.

**2. Why it exists:** operators currently have per-request logs and nothing else — no way to answer "what does this system cost per investigation," "what's our p95 latency by complexity tier," or "which domain agents fail most often" without grepping logs by hand.

**3. Dependencies:** Milestone 3 (event emission must already exist — this milestone builds the aggregation layer on top of it, per §1 point 3's pre-flight fix).

**4. Repository structure:** `metrics/aggregation.py` (new — the collection/write path already exists from M3).

**5. Files to create:** `metrics/aggregation.py`, `data/migrations/versions/0010_metrics.py`, `app/api/v1/admin_metrics.py` (a read-only, `RequireRole(ADMIN)`-gated endpoint surfacing aggregated metrics — not a full dashboard UI, which is explicitly out of scope, see §7), `tests/test_metrics_aggregation.py`, `tests/test_admin_metrics_endpoint.py`.

**6. Files to modify:** none beyond what M3/M8 already wired for event emission.

**7. Public interfaces:**
```python
async def aggregate_metrics(window: str, group_by: Literal["complexity_tier", "domain_agent", "day"]) -> list[MetricRollup]: ...

# GET /api/v1/admin/metrics?window=7d&group_by=complexity_tier  [RequireRole(ADMIN)]
```

**8. Internal classes:** `MetricRollup(group_key, count, p50_latency_ms, p95_latency_ms, avg_cost_estimate, success_rate)`.

**9. Data flow:**
```
[continuous] JobCompleted/IngestionCompleted events (from M3/M8) → metrics table (raw event rows)
GET /admin/metrics → aggregate_metrics(window, group_by) → SELECT ... GROUP BY ... → MetricRollup[]
```

**10. Sequence (text):**
```
Admin Client -> API: GET /admin/metrics?window=7d&group_by=complexity_tier
API -> RequireRole(ADMIN): check
API -> aggregate_metrics: (window="7d", group_by="complexity_tier")
aggregate_metrics -> Postgres: SELECT complexity_tier, percentile_cont(0.5)..., percentile_cont(0.95)..., avg(cost)... FROM metrics WHERE ts > now() - interval '7 days' GROUP BY complexity_tier
Postgres -> aggregate_metrics: rows
API -> Admin Client: 200 {rollups: [...]}
```

**11. Error handling:** an empty result window (no data yet, e.g. right after deployment) → returns an empty-but-valid `MetricRollup[]`, not an error — same "empty is a valid state, not a failure" discipline established since Phase 1's health checks.

**12. Logging requirements:** none new — this milestone consumes logs/events, it doesn't add new ones.

**13. Testing strategy:** Unit — percentile/aggregation SQL correctness against known fixture data (specific, checkable expected p50/p95 values). Integration — real metrics rows inserted via M3/M8's actual emission path, then queried through this milestone's aggregation, proving the whole pipeline end-to-end, not just the aggregation function in isolation. Failure-path — non-admin role → `403`. Edge case — empty window.

**14. CI impact:** none new.

**15. Documentation impact:** `docs/phase3/observability.md` — what's tracked, what isn't (explicitly: this is operational metrics, not the eval harness's reasoning-quality metrics from M5 — the two are related but distinct, and conflating them would be a real documentation failure worth avoiding).

**16. Definition of Done:** a 7-day rollup by complexity tier returns correct, verifiably-accurate p50/p95 latency and cost figures against seeded test data.

**17. Risks:** none significant — this is a read-only aggregation layer over data that already exists by this point in the sequence.

**18. Future extensibility:** `MetricRollup` and the `group_by` parameter are generic enough that a future real dashboard UI (explicitly out of scope here, §7) consumes this exact endpoint without backend rework — the API is the extension point, the UI is future work.

---

### Milestone 10 — Public API Hardening & Versioning

**1. Goal:** Add API-key-based access for external/open-source consumers (distinct from the JWT user-session auth of Milestone 1), formal response-schema stability guarantees, and a deprecation policy — the specific things that matter once other people, not just this team, depend on the API.

**2. Why it exists:** this is the concrete meaning of "assume this repository will become a serious open-source project" for the API surface specifically — external consumers need a stable, documented contract and a way to authenticate that isn't "log in as a human user."

**3. Dependencies:** Milestone 1 (`Role`/`RequireRole` reused, §2's "Future extensibility" note), Milestone 2 (rate limiting extended with an API-key scope).

**4. Repository structure:** `db/models/api_key.py` (already listed in §2).

**5. Files to create:** `data/migrations/versions/0007_api_keys.py`, `app/api/v1/api_keys.py` (create/revoke, `RequireRole(RESEARCHER, ADMIN)`-gated — public-role users can't self-issue API keys, a deliberate anti-abuse decision), `auth/api_key_provider.py` (a second `AuthProvider` implementation, tried after JWT in the middleware's auth chain — see point 9), `docs/api/CHANGELOG.md`, `tests/test_api_keys.py`.

**6. Files to modify:** `gateway/middleware.py`'s composition (auth becomes a small ordered chain — JWT first, then API key — rather than a single provider; this is a genuine, if small, extension of the Protocol-based seam, explicitly justified because Phase 1's single-`AuthProvider` seam always anticipated exactly one real implementation being swapped in, not two coexisting ones — this milestone is where that assumption is revisited, deliberately, not accidentally), `gateway/rate_limiter_redis.py` (new `scope="api_key"` with its own, separate-from-user quota, per M2's `future extensibility` note).

**7. Public interfaces:**
```python
POST /api/v1/api-keys   [RequireRole(RESEARCHER, ADMIN)] → {key: "shown once, never retrievable again", key_id}
DELETE /api/v1/api-keys/{key_id}   [owner or admin]

class ApiKeyAuthProvider:  # second AuthProvider implementation
    async def authenticate(self, request: Request) -> AuthResult | None: ...  # None if no API key header present, allowing the chain to fall through to JWT
```

**8. Internal classes:** `ApiKey` ORM model (hashed key storage — the raw key is never stored, only a hash, mirroring `password_hashing.py`'s existing pattern from Milestone 1, reused rather than reinvented).

**9. Data flow:**
```
POST /api/v1/api-keys [as a logged-in researcher/admin] → generate random key → hash → store → return raw key once
[external consumer] GET /investigations/{id}  [X-API-Key: <key>]
  → GatewayMiddleware: try ApiKeyAuthProvider first (if X-API-Key header present) → else JWTAuthProvider
  → same RequireOwnerOrRole check as any other request from this point on — API-key requests are not a separate authorization path, only a separate authentication path
```

**10. Sequence (text):**
```
Client -> API: GET /investigations/{id}  [X-API-Key: gaios_live_xxxx]
GatewayMiddleware -> ApiKeyAuthProvider: authenticate(request)
ApiKeyAuthProvider -> Postgres: SELECT api_keys WHERE key_hash = hash(provided_key)
alt found and not revoked
  ApiKeyAuthProvider -> GatewayMiddleware: AuthResult(user_id=key.owner_id, role=key.owner.role)
else not found
  ApiKeyAuthProvider -> GatewayMiddleware: None
  GatewayMiddleware -> JWTAuthProvider: authenticate(request)  [fallback]
end
GatewayMiddleware -> RequireOwnerOrRole: [unchanged from M1]
```

**11. Error handling:** revoked/expired key → `401` with a specific `error_code: "api_key_revoked"` distinct from a generic invalid-credential message, since this is a legitimately different, actionable state for an external integrator to see in their own logs.

**12. Logging requirements:** API-key usage logged with `key_id` (never the raw key, and never even the hash in logs — only the non-sensitive `key_id` identifier), enabling per-key usage auditing without any risk of the log stream itself becoming a credential-leakage vector.

**13. Testing strategy:** Unit — key generation/hashing, chain-fallback logic (API key absent → falls through to JWT correctly). Integration — full external-consumer flow: researcher issues a key, a separate "external" test client uses only the key (no JWT) to submit and retrieve an investigation. Failure-path — revoked key rejected, public-role user blocked from self-issuing a key. Edge case — both an API key **and** a JWT present in the same request (decision: API key takes precedence, documented explicitly, since that's the more likely intentional signal from an automated integration).

**14. CI impact:** none structurally new.

**15. Documentation impact:** `docs/api/CHANGELOG.md` established here as the durable, ongoing record of every breaking/non-breaking API change from this point forward — this milestone is also where the project commits to semantic-versioning-style discipline on the public API surface (`/api/v1/` is the current stable surface; any breaking change going forward gets a `/api/v2/` prefix, never a silent in-place change to `v1`) — stated as a policy here because it needs to exist before the first external consumer shows up, not after.

**16. Definition of Done:** an external test client, using only an API key (zero JWT knowledge), can complete a full submit → poll/stream → retrieve flow, and a revoked key is immediately rejected on the next request.

**17. Risks:** key-rotation UX (what happens when a consumer's key needs rotating without downtime) isn't fully designed here — acceptable for Phase 3's actual need (issue/revoke is sufficient for an early open-source project's first external consumers), explicitly flagged as future work rather than silently ignored.

**18. Future extensibility:** the `/api/v1/` vs `/api/v2/` versioning policy stated in point 15 is the concrete mechanism that makes every future phase's API changes safe for external consumers without requiring this milestone to anticipate what those changes will be.

---

## 4. What Was Reconsidered (Per Your Instruction to Redesign If Needed)

You asked me not to blindly follow the existing roadmap and to redesign if I found real blockers. I looked specifically for places where Phase 2's design would break under Phase 3's new requirements, not just places where more features could be bolted on. Two things were genuinely reconsidered, not just extended:

**1. The `AuthProvider` Protocol (Phase 1) was designed for exactly one real implementation to be swapped in.** Milestone 10 needs two (JWT and API key) to coexist. I did not redesign the Protocol itself — it's still correct as a single-method interface — but I explicitly changed how `GatewayMiddleware` is composed (an ordered chain of providers, tried in sequence, first non-`None` result wins) rather than assuming a single provider forever. This is called out explicitly in Milestone 10, point 6, rather than silently smuggled in, because it's a real, if small, revision of an assumption Phase 1 made.

**2. Redis's role needed to be more clearly partitioned before Phase 3 added a queue, a rate limiter, and checkpointing all competing for the same instance.** `RedisKeyBuilder`'s namespacing (`gaiaos:cache:*`, `gaiaos:checkpoint:*`, `gaiaos:ratelimit:*`) already anticipated this correctly back in Phase 2 — I verified it's sufficient for Milestone 3's queue keys too (RQ uses its own internal key conventions, which don't collide with GaiaOS's own namespace, confirmed by checking RQ's default key prefix behavior) and didn't need to add a fourth namespace. No redesign needed here — just confirmation that Phase 2's forward-looking design held up under the load Phase 3 actually puts on it, which is exactly the kind of thing this pre-flight check is supposed to catch (or, in this case, confirm doesn't need catching).

Nothing else warranted reopening. The graph/agent/schema architecture from Phase 2 is sound and every Phase 3 milestone builds on it without modification to its core shape.

---

## 5. End Result

### 5.1 Phase 3 Milestone List
1. Real Authentication & Authorization
2. Real Rate Limiting
3. Durable Task Execution (Redis-Backed Queue)
4. Redis Hardening (Persistence + Checkpoint TTL)
5. Evaluation Harness Expansion + CI Regression Gate
6. Bounded Critic Replan Loop
7. PostGIS Geometry Migration for Hazard Events
8. Real Hazard-Event Ingestion Pipeline
9. Observability & Cost/Latency Metrics
10. Public API Hardening & Versioning

### 5.2 Dependency Graph
```
M1 (Auth)
  │
M2 (Rate Limiting)
  │
M3 (Durable Task Execution) ──────────┐
  │                                    │
M4 (Redis Hardening)                   │
  │                                    │
M5 (Eval Expansion + CI Gate)          │
  │                                    │
M6 (Bounded Replan Loop)               │
                                        │
M7 (PostGIS Geometry) ──── M8 (Real Ingestion) [depends on M3 + M7]
                                        │
M9 (Observability) [depends on M3's event emission]
                                        │
M10 (Public API Hardening) [depends on M1 + M2]
```
M7 has no dependency on M1–M6 and can be built in parallel with that spine if more than one engineer is available; it only needs to complete before M8. M9 only strictly needs M3, so it could also run in parallel with M4–M6 rather than strictly after M6 as numbered — the numbering above is the recommended single-engineer sequence, not a hard requirement for the M9/M7 branches.

### 5.3 Recommended Implementation Order
As numbered (1→10) for a single engineer. With two engineers: one takes the M1→M2→M3→M4→M5→M6 spine, the other takes M7→M8 in parallel (starting once M3 lands, since M8 needs it), with M9 and M10 picked up by whichever engineer frees up first once their branch's prerequisites are met.

### 5.4 Postponed to Phase 4+
- Neo4j migration — scale trigger (>50k causal-graph nodes, or genuine pattern-query need) still not met; M8's real ingestion may eventually approach this, worth re-checking at the start of Phase 4, not before.
- Full MCP wrapping of remaining tool clients (Ocean/Atmosphere/Wildfire) — still no second real MCP consumer beyond the Seismic/Literature servers already built; don't build speculatively.
- Kafka/Kubernetes — still no data-velocity or multi-service-autoscaling trigger.
- A real dashboard UI consuming Milestone 9's metrics endpoint — the API is built, the UI is legitimately separate, larger-scoped work.
- JWT secret rotation strategy (Milestone 1, point 17) and API key rotation UX (Milestone 10, point 17) — both explicitly flagged, not solved, in this phase.
- A third and further ingestion sources beyond USGS/NOAA (Milestone 8, point 18) — the pattern is proven with two, additional sources are low-risk, low-priority follow-on work.

### 5.5 Intentionally Excluded (not postponed — off the table absent a new, separately-justified reason)
- Multi-tenant organizational data isolation (teams/orgs owning investigations collectively, not just individual users) — nothing in this project's actual usage pattern justifies this yet; Milestone 1's per-user ownership model is the right-sized solution for "a serious open-source project" at this stage, and building org-level tenancy now would be exactly the kind of premature infrastructure investment Architecture v1.0 has correctly avoided everywhere else.
- A general plugin system for third-party-contributed domain agents — consistent with the same exclusion stated in the Phase 2 design; still correct, still not revisited.
- Physics-based simulation upgrade — still off the table, no new information in Phase 3 changes this.

### 5.6 Final Architecture Review

Walking the dependency graph forward: M1 gives every later milestone real identity before anything needs to attach ownership or scope access to it. M2 protects the API before M3 makes the thing being protected (durable, worker-consumed job submission) more expensive to abuse. M3 gives M8 a job-scheduling mechanism to reuse instead of inventing a second one, and gives M9 a real event-emission point to build aggregation on top of, both flagged and resolved before implementation rather than discovered mid-build. M4 hardens exactly the mechanism M3 just made load-bearing, immediately, not after it's already been relied upon in production for a while unprotected. M5 produces the real benchmark signal M6 was always explicitly waiting for, honoring a prior architectural decision rather than working around it. M7 corrects the data model before M8 ingests real data into it, avoiding a re-processing pass. M10 reuses M1's role model and M2's rate-limiting infrastructure rather than building parallel versions of either. Every dependency named in §1's pre-flight analysis is satisfied by the point it's needed, not after.

### 5.7 Self-Review Pass

**Question:** if this were implemented exactly as written, would missing architecture surface halfway through?

Checked specifically for: an execution-model change (M3) that isn't instrumented until much later (resolved — M3's own scope explicitly includes minimal event emission, per §1 point 3, rather than deferring all of it to M9); a data migration (M7) that happens after the data it's meant to fix has already been ingested at scale (resolved — M7 is a hard prerequisite of M8, not just recommended ordering); an auth seam (Phase 1's `AuthProvider` Protocol) that turns out not to support the two-provider chain M10 actually needs (caught and explicitly addressed in §4, not silently worked around); a rate limiter built before there's an identity to limit by (resolved via M1→M2 ordering); and a scheduled-job mechanism built twice, once loosely for ingestion and once properly for durable execution (resolved — M8 explicitly reuses M3's worker infrastructure, not a second one).

**Answer: No.** The Phase 3 architecture as sequenced above does not require revision. Proceed to Milestone 1.
