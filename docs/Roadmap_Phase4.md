# GaiaOS — Phase 4 Engineering Design Document

**Role:** Principal Software Architect / Distributed Systems Architect / Security Architect / DevOps Architect
**Status:** Phases 1–3 complete, verified, frozen. Nothing below reopens a completed milestone except where explicitly named as an "absolute blocker" prerequisite, and even those are framed as *finishing a verification gap*, never as redesigning the completed work itself.
**Deliverable type:** design only. No code.

---

## Part A — Architectural Review (Before Any Milestone Is Defined)

### A.1 What the completed architecture actually gives Phase 4 to build on
Three phases in, GaiaOS has: a sound multi-agent reasoning core (Phase 2), and real identity, durability, rate limiting, geospatial correctness, and an eval baseline (Phase 3). This is a genuinely uncommon foundation for an open-source project at this stage — most projects this age either have features and no operational maturity, or operational maturity and a thin feature set. GaiaOS has both. Phase 4's job is not to catch up on fundamentals; it's to do the things that only make sense once fundamentals are solid: real alerting, real disaster recovery, and the specific investments that make a codebase safe for *other people* to contribute to, not just safe for one team to keep extending.

### A.2 Remaining architectural weaknesses (carried in, not newly invented)
1. **Deployment-verification asymmetry.** CI proves the `app` image builds and starts; it has never proven the same for `Dockerfile.worker` or the `scheduler` service. Every Phase 4 milestone that touches workers (and several will) inherits this risk silently unless it's closed first.
2. **Metrics without alerting.** Phase 3 built a queryable metrics API. Nobody is paged when something goes wrong. This is the single largest gap between "the code is good" and "this is production-operable."
3. **Citation matching is text-exact, not identity-based.** This is a latent correctness/robustness risk that scales with literature-corpus size — the more content flows through the Literature/RAG agent, the more claims are at risk of being incorrectly rejected as "unfabricated" citations that simply weren't reproduced verbatim.
4. **Geocoding is honest about failure but still quietly wrong on success** (hardcoded ocean station ID for any non-cached city). A silent-wrong-data class of bug, smaller in blast radius than the one already fixed, but the same category.
5. **No backup/disaster-recovery story.** Postgres and Redis both hold data (investigations, checkpoints, hazard events, users, API keys) with no documented or automated backup, restore drill, or migration-rollback runbook.
6. **No worker-scaling policy.** RQ workers exist; nothing documents or configures how many should run, when to add more, or what "healthy queue depth" looks like. Not urgent at current volume, but exactly the kind of gap that turns into an incident the first time it isn't.
7. **No documented, enforced contribution path for new domain agents.** Every domain agent so far was added by one team reading the existing five and copying the shape. That's fine for one team; it's a real barrier for "a serious long-term open-source platform," where a stranger needs to be able to add a sixth agent (or a hundredth contributor needs to add their first) without reverse-engineering the contract from source.
8. **Supply-chain hygiene still open across three phases.** No lockfile, no automated vulnerability scanning. Correctly deprioritized so far because it scales with team size and external-contributor risk, not with feature count — but an open-source project inherently has more external-contributor risk than a closed team project, which changes the calculus enough to act on it now.
9. **README status table three phases stale.** Not an engineering risk in the traditional sense, but a real credibility and onboarding risk for an open-source project specifically — a stranger's first impression of this repository is currently wrong.

### A.3 Future scaling bottlenecks to design around now (without building prematurely)
- **Worker throughput** is the first thing that will actually bind as query volume grows — not the database, not Redis, not the LLM API (all three have more comfortable headroom at the volumes Architecture v1.0 scoped for). Phase 4 should design the *policy and configuration surface* for scaling workers (so it's a config change, not a redesign, when the time comes) without actually building autoscaling infrastructure that isn't needed yet.
- **Literature corpus growth** interacts with two things at once: the already-known Qdrant migration trigger (documented, not due) and the citation-matching fragility (A.2 item 3) — the second should be fixed *before* corpus growth makes it painful, since it's cheap now and expensive to debug once claims are silently disappearing under real load.
- **Contributor growth**, if this project succeeds as open source, is itself a scaling dimension — more people touching the codebase without a documented extension contract is how architectural drift actually happens in successful open-source projects. This is why A.2 item 7 is treated as an architectural concern, not a "nice to have."

### A.4 Hidden dependencies found while thinking through Phase 4 as a whole
1. **Citation IDs (Evidence schema change) must land before the Agent Contribution Framework's template/documentation is written**, or the framework immediately documents a contract that's about to change underneath new contributors. This is the same class of mistake flagged in the Phase 3 pre-flight analysis (don't build on a soon-to-change shape) — caught again here, resolved by sequencing.
2. **Alerting (on top of metrics) should exist before the Admin Dashboard**, since a dashboard's most valuable content is exactly the alert state a human would otherwise have to infer from raw metrics — building the dashboard first means rebuilding its most important panel once alerting lands.
3. **The worker/scheduler CI-verification gap must close before the worker-scaling milestone**, since designing a scaling policy for a deployment artifact that was never proven to build correctly is designing on sand.
4. **Backup/DR design depends on nothing else in Phase 4** and can run fully in parallel with everything else — flagged explicitly so it isn't accidentally sequenced behind things it doesn't need.

### A.5 Verdict: does the roadmap need to change before implementation?
Yes, in one specific way, stated plainly: **the previous roadmaps' pattern of numbering milestones 1→N as a strict single spine no longer fits Phase 4's actual dependency shape.** Phases 1–3 were each substantially linear (each milestone genuinely needed the one before it). Phase 4's ten milestones split into two mostly-independent tracks — a **Trust & Safety track** (CI integrity, security review, supply chain, backup/DR) and a **Product Maturity track** (alerting, citation IDs, geocoding, worker scaling, contribution framework, dashboard, docs) — with only three real cross-track dependencies (A.4). This isn't a redesign of anything completed; it's an honest acknowledgment that Phase 4's milestones are less linear than Phase 3's, and forcing a fake single-file ordering would be worse engineering than stating the real graph. §D.2 gives both the graph and the recommended single-engineer linearization.

---

## Part B — Complete Repository Structure for Phase 4

```
gaiaos/
├── .github/
│   ├── workflows/
│   │   ├── ci.yml                          # MODIFIED (M1): now builds+smoke-tests worker & scheduler images too
│   │   ├── dependency-audit.yml            # NEW (M1) — scheduled pip-audit / Dependabot-equivalent run
│   │   └── nightly-eval.yml                # unchanged from Phase 3
│   └── dependabot.yml                       # NEW (M1)
│
├── alerting/                                # NEW (M3) — sibling to metrics/, a cross-cutting infra layer
│   ├── __init__.py
│   ├── rules.py                             # threshold/rule definitions, typed, not config-file-driven magic
│   ├── evaluator.py                         # runs on a schedule (worker job), evaluates rules against metrics/aggregation.py
│   ├── notifier.py                          # channel-agnostic notification interface
│   └── channels/
│       ├── webhook.py                       # NEW — generic outbound webhook (Slack/Discord/PagerDuty-compatible payload)
│       └── email.py                         # reuses auth/email_service.py's transport, not a second email client
│
├── orchestrator/schemas/
│   └── agent_io.py                          # MODIFIED (M4): Evidence gains a stable `id: UUID` field
├── orchestrator/agents/synthesis/
│   └── citation_mapper.py                   # MODIFIED (M4): ID-based matching, text-matching retained only as a fallback for evidence pre-dating the migration
│
├── tools/
│   ├── geocoding.py                          # MODIFIED (M5): dynamic NOAA station resolution, docstring corrected
│   └── http_client.py                        # NEW (M5) — shared, pooled httpx.AsyncClient factory, used by every tool client instead of one-per-call instantiation
│
├── ops/                                       # NEW (M6) — operational runbooks and backup tooling, deliberately not under docs/ since it's executable tooling + procedure, not narrative documentation
│   ├── backup/
│   │   ├── postgres_backup.py                # scheduled logical backup job (pg_dump-based), registered on the existing RQ-scheduler
│   │   ├── redis_backup.py                   # RDB snapshot verification job (AOF already provides durability; this verifies snapshot integrity, doesn't duplicate it)
│   │   └── restore_drill.py                  # a runnable, testable restore procedure — not just a markdown runbook
│   └── runbooks/
│       ├── incident_response.md
│       ├── migration_rollback.md
│       └── disaster_recovery.md
│
├── workers/
│   └── scaling_policy.py                     # NEW (M7) — worker-pool-sizing configuration surface (not autoscaling infrastructure itself)
│
├── docs/
│   ├── CONTRIBUTING_AGENTS.md                 # NEW (M8) — the enforced, documented pattern for adding a new domain agent
│   └── phase4/                                 # NEW — per-milestone docs, mirrors docs/phase3/
│
├── scripts/
│   └── new_agent_template/                    # NEW (M8) — a copyable scaffold (not a dynamic plugin loader) for a new domain agent
│       ├── __init__.py.template
│       ├── agent.py.template
│       └── test_agent.py.template
│
├── admin_ui/                                   # NEW (M9) — the first genuine frontend in this repository
│   ├── package.json
│   ├── src/
│   │   ├── pages/{Metrics,Alerts,Investigations}.tsx
│   │   └── api/client.ts                       # thin client against the existing /api/v1/admin/* surface — no new backend logic, purely a consumer
│   └── Dockerfile.admin_ui                     # a fourth, independent deployable — never imports backend Python code
│
├── README.md                                   # MODIFIED (M10) — full status-table rewrite
└── docs/api/openapi/                           # NEW (M10) — published, versioned OpenAPI spec, generated from FastAPI's existing schema, not hand-maintained
```

**Dependency direction, extended:**
- `alerting → metrics, cache` only. Never `alerting → app` — alerts are evaluated by a scheduled worker job (reusing M3-of-Phase-3's scheduler), not by the API process, exactly mirroring the ingestion job pattern already established.
- `ops/backup → db, cache` only, invoked as scheduled worker jobs — no new execution mechanism, extending the existing scheduler pattern for the third time (ingestion, then this), which is itself a sign the Phase 3 worker/scheduler investment is paying for itself.
- `admin_ui → nothing in this codebase at build time` — it's a separate Node/TypeScript project consuming the existing HTTP API like any external client would, deliberately proving the API-versioning discipline from Phase 3's Milestone 10 by being its first real "external" consumer.
- `tools/http_client.py → config` only — a shared factory, imported by every existing tool client, replacing (not duplicating) their individual `httpx.AsyncClient()` instantiations.

---

## Part C — Milestones

### Milestone 1 — CI/Deployment Integrity Completion + Supply-Chain Hardening

**1. Goal:** Close the worker/scheduler CI-verification gap; add a dependency lockfile and automated vulnerability scanning.
**2. Why it exists:** Every later Phase 4 milestone that touches a worker (M3, M6, M7) inherits this risk if it isn't closed first (A.4.3). Supply-chain hygiene matters more now that the project is explicitly positioning as long-term open source (A.2.8).
**3. Dependencies:** none — root of the Trust & Safety track.
**4. Architectural rationale:** this is verification-and-hygiene work, not a redesign; it makes an existing, correct artifact (Dockerfile.worker) provably correct rather than assumed correct.
**5. Repository structure changes:** `.github/workflows/dependency-audit.yml`, `.github/dependabot.yml` (both new, §B).
**6. Files to create:** the two above, plus a generated `requirements/base.lock` / `requirements/dev.lock` (via `pip-compile`), `tests/test_worker_image_smoke.py` (a CI-invoked smoke script, not a pytest unit test per se, but tracked alongside tests for visibility).
**7. Files to modify:** `.github/workflows/ci.yml` (extend the existing `docker compose up --build --wait` step to include `worker` and `scheduler`, with a job-processing smoke test — enqueue a trivial no-op job, assert a worker picks it up and completes it within a timeout).
**8. Public interfaces:** none — this is infrastructure, not application code.
**9. Internal classes:** none new.
**10. Data flow:** `CI → docker compose up --build --wait app worker scheduler → enqueue smoke job → assert completion → teardown`.
**11. Sequence (text):**
```
CI -> Docker: build app, worker, scheduler images
CI -> Compose: up --wait (all three + postgres + redis)
CI -> API: POST /internal/smoke-job  [a trivial, CI-only enqueue endpoint, gated to non-prod envs]
CI -> Postgres: poll job status
alt completes within timeout
  CI -> pass
else
  CI -> fail, dump worker logs
end
```
**12. Database changes:** none.
**13. Redis changes:** none.
**14. API changes:** one new, deliberately non-production endpoint (`/internal/smoke-job`, gated by `Settings.GAIAOS_ENV != "prod"` at minimum, ideally also behind a CI-only shared secret) — this is infrastructure test tooling, not a feature, and must never be reachable in production; stated explicitly so it isn't forgotten.
**15. Event flow:** the smoke job publishes a normal `JobStarted`/`JobCompleted` metrics event, verifying the metrics pipeline as a side effect.
**16. Background worker interactions:** this milestone's entire point is verifying worker interaction — it is the worker interaction being tested.
**17. Error handling:** CI must fail loudly (worker logs dumped as a build artifact) on smoke-job timeout, not silently skip.
**18. Logging requirements:** none new beyond what already exists.
**19. Metrics to expose:** none new.
**20. Security considerations:** the smoke endpoint is the one real risk in this milestone — an accidentally-production-reachable job-injection endpoint is a genuine attack surface; the environment gate is non-negotiable and should itself be tested (a test asserting the endpoint 404s when `GAIAOS_ENV=prod`).
**21. Performance considerations:** none — this runs only in CI.
**22. Scalability considerations:** none.
**23. Testing strategy:** the CI smoke test itself is the primary test; additionally, a unit test asserting the smoke endpoint is unreachable outside non-prod environments.
**24. CI impact:** this milestone *is* a CI change.
**25. Documentation impact:** `docs/phase4/ci_deployment_verification.md`.
**26. Migration strategy:** none — no schema change.
**27. Rollback strategy:** revert the CI workflow change; no data migration to roll back.
**28. Definition of Done:** a deliberately-broken `Dockerfile.worker` (e.g., a missing `COPY`, reproducing the exact Phase 2 bug class on purpose in a throwaway test branch) is caught by the new CI step before merge.
**29. Risks:** the smoke endpoint's environment gate is the one thing that must not be gotten wrong — treat its test coverage as non-negotiable, mirroring the "least-negotiable test suite" framing used for `CitationMapper` in the Phase 2 design.
**30. Future extensibility:** the same smoke-job pattern extends to any future fourth deployable (e.g., a future dedicated ingestion-worker image) without new design.

**Success Criteria:**
- *Verification:* the deliberately-broken-Dockerfile test in point 28 is the concrete proof.
- *Tests required:* CI smoke test (all three images), unit test for the environment-gate on `/internal/smoke-job`.
- *CI changes:* as described throughout.
- *Audit findings eliminated:* Part 2/Milestone 3 and Part 4 findings from the Phase 3 audit ("worker/scheduler images unverified by CI").
- *Debt intentionally left behind:* none from this milestone's own scope; the lockfile is a snapshot at a point in time and will need periodic regeneration, which is normal maintenance, not debt.

---

### Milestone 2 — Security Review & Hardening of Authentication Extensions

**1. Goal:** Formal security review of `auth/email_service.py` (flagged as an unreviewed, undocumented scope addition in the Phase 3 audit), closing that gap before Phase 4 builds anything further on top of authentication (dashboard admin sessions, alert-notification preferences).
**2. Why it exists:** named directly in the Phase 3 audit as needing review before being trusted for anything password-reset-adjacent; Phase 4 is the first opportunity to close it before further auth-adjacent features are added.
**3. Dependencies:** none.
**4. Architectural rationale:** this is a review-and-harden milestone, not new scope — the file already exists; this milestone's job is to bring it up to the same bar as the rest of the auth package (which was reviewed carefully in Phase 3) or fix it until it is.
**5. Repository structure changes:** none — no new files unless the review finds something requiring one (e.g., a token-expiry table, if none exists).
**6. Files to create:** `tests/test_email_service_security.py` (host-header injection in reset links, token predictability/entropy, expiry enforcement, rate limiting on reset requests specifically — separate from the general API rate limiter, since password-reset endpoints are a classic targeted-abuse vector that deserves its own, tighter limit).
**7. Files to modify:** `auth/email_service.py` itself, as needed by review findings — cannot be fully specified until the review happens, which is itself the correct, honest way to scope a security-review milestone rather than pretending to know its findings in advance.
**8. Public interfaces:** unchanged unless review findings require a signature change (e.g., adding an explicit token-expiry parameter if one is missing).
**9. Internal classes:** review whether a dedicated `PasswordResetToken` model/table exists with proper expiry and single-use enforcement; if not, add one rather than patching an ad hoc mechanism.
**10. Data flow:** `POST /auth/request-reset → generate single-use, time-limited token → email_service sends reset link → POST /auth/reset {token, new_password} → verify token (unused, unexpired) → update password → invalidate token`.
**11. Sequence (text):**
```
Client -> API: POST /auth/request-reset {email}
API -> UserRepository: get_by_email(email)
API -> PasswordResetToken: create(user_id, expires_in=15min)
API -> email_service: send_reset_email(user.email, token)
API -> Client: 202 {message: "if this email exists, a reset link was sent"}  [never reveals whether the email exists]

Client -> API: POST /auth/reset {token, new_password}
API -> PasswordResetToken: validate(token)  [unused AND unexpired]
alt valid
  API -> password_hashing: hash(new_password)
  API -> UserRepository: update_password(user_id, new_hash)
  API -> PasswordResetToken: mark_used(token)
  API -> Client: 200
else
  API -> Client: 400 {error_code: "invalid_or_expired_token"}
end
```
**12. Database changes:** likely a new `password_reset_tokens` table if review finds none exists (token hash, user_id, expires_at, used_at).
**13. Redis changes:** a per-email rate limit specifically on `/auth/request-reset` (reusing `RedisRateLimiter` with a dedicated `scope="password_reset"`), since this endpoint is a common target for enumeration/abuse regardless of the general API rate limit.
**14. API changes:** `/auth/request-reset` response must be identical whether the email exists or not (point 11) — a specific, testable non-enumeration requirement.
**15. Event flow:** none new beyond standard request logging.
**16. Background worker interactions:** none — this flow is synchronous, appropriately (email sending can be fire-and-forget via a queued job if latency matters, but correctness doesn't require it, and adding a queue here purely for this would be the kind of unnecessary complexity the design principles ask to avoid).
**17. Error handling:** never reveal account existence via timing or response differences — worth an explicit test (response time for existing vs. non-existing email should not be meaningfully distinguishable, a real, checkable property, not just an aspiration).
**18. Logging requirements:** reset requests logged with `user_id` (only if found — never log the attempted email if not found, to avoid building a de facto enumeration log), never the token or token hash.
**19. Metrics to expose:** reset-request rate (feeds M3's alerting — a spike here is a real abuse signal worth alerting on).
**20. Security considerations:** this entire milestone is a security consideration — the specific checklist is: token entropy (cryptographically random, sufficient length), single-use enforcement, expiry enforcement, non-enumeration, dedicated rate limiting, and host-header safety in the generated reset link (use a configured base URL from `Settings`, never `request.headers["host"]`, which is a classic reset-link-poisoning vector).
**21. Performance considerations:** negligible — low-frequency endpoint.
**22. Scalability considerations:** none.
**23. Testing strategy:** the full checklist in point 20, each as an explicit, named test — this is exactly the kind of security-critical surface where "we reviewed it" needs to mean "here are the tests that prove it," not a sign-off with no artifact.
**24. CI impact:** none structurally new.
**25. Documentation impact:** `docs/phase4/auth_security_review.md` — the findings and fixes, explicitly, so this milestone's existence is traceable (a security review with no written findings is not a security review).
**26. Migration strategy:** the new `password_reset_tokens` table (if needed) via a standard Alembic migration.
**27. Rollback strategy:** standard `alembic downgrade` for the schema change; the endpoint behavior change (non-enumeration response) has no data to roll back.
**28. Definition of Done:** every item in point 20's checklist has a passing, named test; host-header-based link poisoning is specifically demonstrated-and-blocked in a test, not just asserted safe.
**29. Risks:** if the review finds `email_service.py` has a more serious pre-existing issue (e.g., tokens that were never expiring), this milestone's scope could grow — acceptable, since finding that *is* this milestone succeeding at its job, not scope creep.
**30. Future extensibility:** the dedicated `password_reset` rate-limit scope and the non-enumeration pattern are the template for any future sensitive-action endpoint (e.g., a future account-deletion flow) without needing new design.

**Success Criteria:**
- *Verification:* the full security checklist (point 20) passes as named, automated tests.
- *Tests required:* token entropy/expiry/single-use, non-enumeration timing, host-header-safety, dedicated rate-limit scope.
- *CI changes:* none beyond the new test file running in the existing suite.
- *Audit findings eliminated:* the Phase 3 audit's "unreviewed `email_service.py`" finding, precisely.
- *Debt intentionally left behind:* none expected; if review finds issues requiring a larger rework than fits this milestone, that becomes an explicit, named Phase 4.5/Phase 5 item, not silently absorbed.

---

### Milestone 3 — Production Monitoring & Alerting

**1. Goal:** Build a real alerting layer on top of Phase 3's metrics API — threshold-based rules, evaluated on a schedule, notifying via a channel-agnostic interface (webhook first, since it covers Slack/Discord/PagerDuty/Opsgenie-compatible integrations with one implementation).
**2. Why it exists:** named directly as accepted backlog ("production monitoring & alerting"); this is the single most consequential production-readiness gap identified across all three prior audits.
**3. Dependencies:** Phase 3's `metrics/aggregation.py` (must exist — it does).
**4. Architectural rationale:** alerting is evaluated by a scheduled worker job, not the API process — this is the third reuse of the scheduler pattern (ingestion, then backup in M6, now this), which is exactly the "duplicated infrastructure" the design principles ask to avoid; reusing it here instead of inventing a fourth scheduling mechanism is a deliberate, positive architectural decision, not a default.
**5. Repository structure changes:** `alerting/` (new, §B).
**6. Files to create:** `alerting/{__init__.py,rules.py,evaluator.py,notifier.py}`, `alerting/channels/webhook.py`, `workers/jobs/alert_evaluation_job.py`, `data/migrations/versions/00XX_alert_rules_and_incidents.py`, `tests/test_alert_rules.py`, `tests/test_alert_evaluator.py`, `tests/test_webhook_notifier.py`.
**7. Files to modify:** `workers/scheduler.py` (register the new evaluation job), `config/settings.py` (`ALERT_EVALUATION_INTERVAL_MINUTES`, `ALERT_WEBHOOK_URL`).
**8. Public interfaces:**
```python
class AlertRule(BaseModel):
    name: str
    metric: str            # e.g. "investigation.p95_latency_ms"
    threshold: float
    comparison: Literal["gt", "lt"]
    window: str             # e.g. "15m"
    severity: Literal["warning", "critical"]

async def evaluate_rules(rules: list[AlertRule]) -> list[AlertFiring]: ...
async def notify(firing: AlertFiring, channel: NotificationChannel) -> None: ...
```
**9. Internal classes:** `AlertFiring(rule_name, current_value, threshold, severity, fired_at)`, `AlertIncident` (a DB-persisted record of a firing/resolution pair — so alerts have a history, not just a fire-and-forget notification), `WebhookNotificationChannel` (implements a small `NotificationChannel` Protocol, mirroring the `AuthProvider`/`RateLimiter` Protocol pattern already established twice in this codebase — a third, consistent application of the same design idiom, not a new one).
**10. Data flow:**
```
Scheduler (every N minutes) → enqueue evaluate_alerts_job
Worker → evaluate_alerts_job
  → evaluate_rules(configured rules) against metrics/aggregation.py's existing rollups
  → for each firing: check AlertIncident table for an already-open incident of the same rule (avoid duplicate notifications for a still-firing condition)
  → if new firing: create AlertIncident, notify(firing, webhook_channel)
  → if a previously-firing rule is no longer firing: resolve the AlertIncident, notify a resolution message
```
**11. Sequence (text):**
```
RQ-Scheduler -> Redis: trigger (every 5 min, configurable)
Worker -> alert_evaluation_job: run()
alert_evaluation_job -> evaluator: evaluate_rules(configured_rules)
evaluator -> metrics/aggregation: aggregate_metrics(window, group_by)
metrics/aggregation -> Postgres: SELECT ...
evaluator -> alert_evaluation_job: AlertFiring[]
loop for each firing
  alert_evaluation_job -> Postgres: check open AlertIncident for this rule
  alt new firing
    alert_evaluation_job -> Postgres: INSERT AlertIncident
    alert_evaluation_job -> notifier: notify(firing, webhook)
    notifier -> Webhook URL: POST payload
  else already open
    alert_evaluation_job -> [no-op, avoid duplicate notification]
  end
end
loop for each previously-open incident no longer firing
  alert_evaluation_job -> Postgres: UPDATE AlertIncident SET resolved_at
  alert_evaluation_job -> notifier: notify(resolution)
end
```
**12. Database changes:** new `alert_incidents` table (rule_name, severity, fired_at, resolved_at, last_value) — deliberately a table, not just a log line, so incident history is queryable (feeds M9's dashboard directly).
**13. Redis changes:** none beyond the existing scheduler mechanism.
**14. API changes:** `GET /api/v1/admin/alerts` (list current + historical incidents, `RequireRole(ADMIN)`), `POST /api/v1/admin/alert-rules` (create/modify rules — admin-only, since rule misconfiguration is itself an operational risk).
**15. Event flow:** alert firing/resolution could optionally also publish to the existing SSE/Redis pub-sub mechanism for a live admin dashboard feed — noted as a natural fit for M9's dashboard, not built until then, to keep this milestone scoped to alerting itself.
**16. Background worker interactions:** the evaluation job is itself a worker job, exactly like ingestion — the same failure-handling pattern applies (a failed evaluation cycle doesn't lose incident state, just delays the next check).
**17. Error handling:** a failed metric-aggregation query (e.g., DB temporarily unavailable) must not itself trigger a false alert or crash the evaluation job — caught, logged, retried next cycle, exactly like ingestion's cursor-based retry pattern.
**18. Logging requirements:** every evaluation cycle logged with `rules_evaluated`, `firings_found`, `notifications_sent`.
**19. Metrics to expose:** meta-metrics about alerting itself — `alert_evaluation_duration_ms`, `notification_failures` (an alerting system that can silently fail to notify is worse than no alerting system, so its own failure mode needs its own visibility — a deliberate, non-obvious requirement worth stating explicitly).
**20. Security considerations:** the webhook URL is a secret (stored via `Settings`, never logged); rule creation is admin-gated specifically because a malicious or mistaken rule change (e.g., silencing a real alert) is itself a security-relevant action.
**21. Performance considerations:** evaluation runs on a schedule, not per-request — no impact on API latency by design.
**22. Scalability considerations:** rule evaluation cost scales with rule count, not investigation count — a deliberate design choice that keeps this milestone's cost bounded and predictable regardless of query volume growth.
**23. Testing strategy:** Unit — threshold comparison logic, duplicate-notification suppression. Integration — full evaluation cycle against seeded metrics data, asserting correct firing/resolution transitions. Failure-path — webhook endpoint unreachable → asserts the failure is itself logged/counted (point 19), not silently swallowed. Edge case — a rule that fires and resolves within the same evaluation cycle (rapid flapping) — decide and test a specific behavior (e.g., require N consecutive firing cycles before notifying, to avoid alert fatigue from flapping metrics) rather than leaving it undefined.
**24. CI impact:** none structurally new beyond the existing worker-job test patterns.
**25. Documentation impact:** `docs/phase4/alerting.md` — the default rule set and rationale, the flapping-suppression policy from point 23.
**26. Migration strategy:** standard Alembic migration for `alert_incidents`.
**27. Rollback strategy:** standard `alembic downgrade`; disabling alerting entirely is a single settings flag (`ALERTING_ENABLED=false`), not a code change, matching the feature-flag discipline established in Phase 3.
**28. Definition of Done:** a deliberately-induced condition (e.g., a seeded metric value crossing a configured threshold in a test) results in exactly one webhook notification, a persisted incident record, and a subsequent resolution notification once the condition clears — the full lifecycle proven, not just the firing half.
**29. Risks:** alert-rule tuning (what thresholds actually matter) is a genuine judgment call, not an engineering one — ship with a small, conservative default rule set (e.g., p95 latency, job failure rate, ingestion failure rate) rather than trying to anticipate every useful rule up front.
**30. Future extensibility:** the `NotificationChannel` Protocol means a future Slack-specific or PagerDuty-specific channel is a second small implementation, not a rework — webhook covers the common case now, without over-building.

**Success Criteria:**
- *Verification:* the full firing→resolution lifecycle test in point 28.
- *Tests required:* threshold logic, duplicate suppression, flapping policy, webhook failure visibility.
- *CI changes:* none beyond new tests in the existing suite.
- *Audit findings eliminated:* "no real alerting layer" — the single largest named gap across all three prior audits.
- *Debt intentionally left behind:* only webhook notifications in Phase 4 (no native Slack/email-specific formatting) — explicitly acceptable, generic webhook payloads are compatible with every major platform's incoming-webhook format already.

---

### Milestone 4 — Citation Integrity Upgrade (Evidence IDs)

**1. Goal:** Give `Evidence` a stable `id: UUID` field and migrate `CitationMapper` from exact-text matching to ID-based matching, closing a design-risk flagged (and left open) across two prior audits.
**2. Why it exists:** named directly as accepted backlog ("citation identifiers"); the fix is small, well-understood, and strictly more robust than the current approach — there is no reason to defer it further, and every additional phase of literature-corpus growth increases the cost of leaving it unfixed (A.3).
**3. Dependencies:** none — this milestone must complete *before* M8 (Agent Contribution Framework) documents the agent contract, per A.4.1.
**4. Architectural rationale:** this is a schema and prompt-contract change, not a new subsystem — `Evidence` already exists, this milestone adds one field and changes how the LLM is asked to reference it.
**5. Repository structure changes:** none — modifications only.
**6. Files to create:** `tests/test_citation_id_matching.py`.
**7. Files to modify:** `orchestrator/schemas/agent_io.py` (`Evidence.id: UUID = Field(default_factory=uuid4)`), every domain agent that constructs `Evidence` objects (a mechanical change — the ID is generated at construction, agents don't need to supply it manually), `orchestrator/agents/synthesis/agent.py`'s system prompt (instruct the model to cite by `evidence_id`, not by reproducing claim text), `orchestrator/agents/synthesis/citation_mapper.py` (`_find_matching_evidence` becomes an ID lookup; **text-matching is retained as a fallback path**, not deleted outright, specifically to handle any evidence that predates this migration in a long-running system, or a model response that ignores the new instruction and still reproduces text — graceful degradation, not a hard cutover that breaks on the first imperfect model response).
**8. Public interfaces:**
```python
class Evidence(BaseModel):
    id: UUID = Field(default_factory=uuid4)   # NEW
    source: str
    claim: str
    confidence: float
    retrieved_at: datetime
```
**9. Internal classes:** `CitationMapper._find_matching_evidence` now tries ID lookup first, falls back to the existing text-normalization match only if no `evidence_id` was cited or the cited ID doesn't resolve — logged distinctly (`citation.matched_by_id` vs. `citation.matched_by_text_fallback`) so the fallback rate itself is a measurable signal of how well the new instruction is working in practice.
**10. Data flow:** unchanged structurally — `Evidence` objects flow through the graph exactly as before, now carrying a stable ID from the moment they're created by any domain agent.
**11. Sequence (text):**
```
DomainAgent -> Evidence: construct(id=uuid4(), source, claim, confidence)
Synthesis -> LLM: "cite using evidence_id, e.g. [cite: <uuid>]"
LLM -> Synthesis: claims with evidence_id references
Synthesis -> CitationMapper: validate(claims, evidence_pool)
CitationMapper -> CitationMapper: try match by evidence_id
alt id found in pool
  CitationMapper -> Synthesis: claim accepted
else id not found or absent
  CitationMapper -> CitationMapper: fall back to text-normalization match [existing Phase 2 logic, unchanged]
  alt text match found
    CitationMapper -> Synthesis: claim accepted [logged: matched_by_text_fallback]
  else
    CitationMapper -> Synthesis: claim rejected [existing behavior, unchanged]
  end
end
```
**12. Database changes:** none — `Evidence` is not itself a persisted table; it lives in graph state and `execution_trace` JSONB, so this is a shape change to in-flight/logged data, not a migration.
**13. Redis changes:** none.
**14. API changes:** `execution_trace` JSONB responses now include `evidence_id` per citation — additive, non-breaking (per Phase 3's own `/api/v1` vs `/api/v2` policy, an additive field doesn't require a version bump).
**15. Event flow:** none new.
**16. Background worker interactions:** none new — this runs inside the existing investigation job, unchanged.
**17. Error handling:** unchanged from the existing Synthesis/Critic error-handling patterns — this milestone changes *how* a citation is validated, not what happens when validation fails.
**18. Logging requirements:** the `matched_by_id` vs. `matched_by_text_fallback` distinction from point 9 — this is genuinely new, valuable signal, not just incidental logging.
**19. Metrics to expose:** `citation_fallback_rate` (what fraction of citations needed the text-matching fallback) — feeds M3's alerting as a candidate future rule (a rising fallback rate could indicate the LLM is drifting away from following the new citation instruction, worth knowing about operationally).
**20. Security considerations:** none new — this doesn't change the trust boundary, only the matching mechanism.
**21. Performance considerations:** ID lookup (a dict/set membership check) is strictly cheaper than the existing text-normalization comparison — a small, genuine performance improvement as a side effect, not the point of the milestone but worth noting.
**22. Scalability considerations:** ID-based matching doesn't degrade as literature-corpus size grows the way text-matching's false-rejection risk does (A.2.3) — this is the actual scalability justification for doing this now rather than later.
**23. Testing strategy:** Unit — ID-match success, ID-match-miss-falls-back-to-text, text-fallback success and failure (retaining Phase 2's existing test coverage for the fallback path, not discarding it). Integration — a full Synthesis run where the model is prompted with the new instruction and correctly cites by ID. Failure-path — a fabricated `evidence_id` that doesn't exist in the pool → correctly rejected, exactly like a fabricated text citation was before. Edge case — a model response that ignores the ID instruction entirely and reproduces text verbatim → correctly caught by the fallback, proving graceful degradation actually works, not just exists in theory.
**24. CI impact:** none new.
**25. Documentation impact:** `docs/phase4/citation_integrity.md` — explicitly documents that this is *additive*, not a breaking change to the agent contract, since M8 will need to state this precisely when documenting the contract for new contributors.
**26. Migration strategy:** none (no schema change, per point 12).
**27. Rollback strategy:** revert the prompt instruction and matching-order change; the `id` field itself is harmless to leave in place even if rolled back (unused, not breaking).
**28. Definition of Done:** the fallback-path test (point 23's edge case) passes, proving the migration is genuinely non-breaking for imperfect model behavior, not just correct in the happy path.
**29. Risks:** none significant — this is a well-understood, low-blast-radius fix specifically because the fallback path is retained rather than the old behavior being deleted outright.
**30. Future extensibility:** once `citation_fallback_rate` (point 19) is observed to be consistently near-zero over enough real usage, the text-matching fallback becomes a candidate for removal in a future phase — not decided now, explicitly deferred to real operational evidence, consistent with this project's established discipline of not making changes ahead of the evidence that justifies them.

**Success Criteria:**
- *Verification:* the graceful-degradation edge-case test (point 23).
- *Tests required:* as listed in point 23, in full.
- *CI changes:* none.
- *Audit findings eliminated:* "CitationMapper exact-text matching, no evidence IDs" — flagged in both the Phase 2 and Phase 3 audits.
- *Debt intentionally left behind:* the text-matching fallback path remains in the codebase indefinitely until real fallback-rate data justifies removing it — a deliberate, named, evidence-gated piece of retained complexity, not an oversight.

---

### Milestone 5 — Geocoding & Tool-Client Data Quality

**1. Goal:** Replace the hardcoded ocean `station_id` fallback with dynamic NOAA station resolution (nearest-station lookup from resolved coordinates); correct the stale geocoding docstring; introduce a shared, pooled HTTP client factory for all tool clients.
**2. Why it exists:** the station-ID item is named accepted backlog; the pooled-client fix closes a Phase 2-flagged performance finding that's remained open across two phases and is cheap to fix once, centrally, rather than N times per tool client.
**3. Dependencies:** none.
**4. Architectural rationale:** bundling these three items into one milestone is deliberate — all three touch the same small surface (`tools/`) and none individually justifies a full milestone's overhead on its own; this is right-sized scoping, not scope-stuffing.
**5. Repository structure changes:** `tools/http_client.py` (new, §B).
**6. Files to create:** `tools/http_client.py`, `tests/test_shared_http_client.py`, `tests/test_dynamic_station_lookup.py`.
**7. Files to modify:** `tools/geocoding.py` (dynamic station lookup via NOAA's station-metadata API — find the nearest station to resolved coordinates, not a hardcoded constant; docstring corrected to describe the actual current behavior), every tool client under `tools/` (`seismic_usgs`, `ocean_noaa`, `weather`, `wildfire_firms`) switched from per-call `httpx.AsyncClient()` instantiation to the shared factory.
**8. Public interfaces:**
```python
# tools/http_client.py
def get_shared_client() -> httpx.AsyncClient: ...   # process-lifetime singleton, closed on app/worker shutdown

# tools/geocoding.py
async def resolve_nearest_station(lat: float, lon: float, network: str = "noaa") -> str: ...
```
**9. Internal classes:** none new beyond the client factory itself.
**10. Data flow:** `geocode(location) → (lat, lon) → resolve_nearest_station(lat, lon) → real station_id → OceanAgent uses it, no longer hardcoded`.
**11. Sequence (text):**
```
CausalChainAgent/OceanAgent -> geocoding: geocode(location)
geocoding -> Open-Meteo API: lookup
Open-Meteo API -> geocoding: (lat, lon)
geocoding -> resolve_nearest_station: (lat, lon)
resolve_nearest_station -> NOAA Station Metadata API: nearest-station query
NOAA API -> resolve_nearest_station: station_id
geocoding -> caller: {lat, lon, station_id}
```
**12. Database changes:** none.
**13. Redis changes:** station-lookup results are a good caching candidate (station metadata changes essentially never) — cache via the existing `RedisKeyBuilder` cache namespace with a long TTL (e.g., 30 days), avoiding a redundant NOAA API call on every geocoding request for a repeated location.
**14. API changes:** none.
**15. Event flow:** none new.
**16. Background worker interactions:** none new.
**17. Error handling:** station-lookup failure → falls back to the existing `AgentOutput.errors` gap-disclosure pattern (consistent with every other tool failure in this codebase), never to the old hardcoded constant — the fix must not reintroduce the same silent-wrong-data shape it's replacing.
**18. Logging requirements:** cache hit/miss for station lookups (operational visibility into whether the caching is actually effective).
**19. Metrics to expose:** station-lookup cache hit rate.
**20. Security considerations:** none new — NOAA's station API is a public, unauthenticated data source, same trust level as the sources already integrated.
**21. Performance considerations:** the shared client factory is the direct fix for the Phase 2-flagged per-call connection overhead — a genuine, measurable latency improvement for any tool making repeated calls within a single investigation's fan-out.
**22. Scalability considerations:** connection pooling matters more as concurrent investigation volume grows (Part 5 of the Phase 3 audit) — this is the right phase to fix it, before volume makes the current per-call cost more noticeable.
**23. Testing strategy:** Unit — nearest-station distance calculation against known fixture coordinates. Integration — mocked NOAA station API (same `respx` pattern used throughout this codebase), full geocode-then-resolve flow. Failure-path — station API unreachable → explicit gap, not a crash, not a silent fallback to a constant. Edge case — a location with no nearby station within a reasonable radius → explicit gap, correctly distinguished from a plain API failure.
**24. CI impact:** none new.
**25. Documentation impact:** `docs/phase4/geocoding_data_quality.md`.
**26. Migration strategy:** none.
**27. Rollback strategy:** revert to the hardcoded constant is trivial if needed, though there's no reason to expect needing it.
**28. Definition of Done:** a query about a city outside the original 8-entry local cache returns ocean data from a station actually near that city, verified against known-correct station assignments for at least 3 test cities.
**29. Risks:** NOAA's station-metadata API shape/availability is an external dependency risk, mitigated the same way every other external source in this codebase is (mocked tests, explicit-gap failure handling).
**30. Future extensibility:** the shared HTTP client factory is now the standard for any future tool client (a seventh domain agent's data source, per M8's contribution framework) — documented as the required pattern, not left to each new contributor to discover independently.

**Success Criteria:**
- *Verification:* the 3-city station-correctness test in point 28.
- *Tests required:* as listed in point 23.
- *CI changes:* none.
- *Audit findings eliminated:* "hardcoded ocean station_id," "unpooled httpx.AsyncClient per call" — both named across the Phase 2/3 audits.
- *Debt intentionally left behind:* the original 8-entry local geocoding cache remains as a fast-path optimization (unchanged, still correctly justified as a performance win, not a correctness crutch now that the failure/fallback paths are both fixed).

---

### Milestone 6 — Backup, Disaster Recovery & Migration Rollback Tooling

**1. Goal:** Automated, scheduled Postgres backups; Redis snapshot integrity verification; a runnable (not just narrative) restore drill; documented incident-response and migration-rollback runbooks.
**2. Why it exists:** named directly in the Phase 3 audit's production-readiness gaps ("no backup strategy... no documented rollback procedure... no backup/restore drill"). This is pure operational maturity work with no dependency on anything else in Phase 4.
**3. Dependencies:** none — can run fully in parallel with every other Phase 4 milestone (A.4.4).
**4. Architectural rationale:** backup/restore is implemented as *runnable tooling*, not just markdown instructions — a runbook that's never been executed is not a verified capability, it's a hope. `ops/backup/restore_drill.py` is a script that actually performs a restore into a scratch environment and verifies data integrity, runnable on demand and ideally on a schedule (e.g., monthly) as its own form of continuous verification.
**5. Repository structure changes:** `ops/` (new top-level directory, §B) — deliberately not under `docs/`, since it contains executable tooling alongside procedure documentation, and conflating "things you read" with "things you run" would be a real structural smell.
**6. Files to create:** `ops/backup/{postgres_backup.py,redis_backup.py,restore_drill.py}`, `ops/runbooks/{incident_response.md,migration_rollback.md,disaster_recovery.md}`, `workers/jobs/backup_jobs.py`, `tests/test_backup_jobs.py`, `tests/test_restore_drill.py`.
**7. Files to modify:** `workers/scheduler.py` (register scheduled backup jobs — the scheduler's third registered job type, after ingestion and alerting), `config/settings.py` (`BACKUP_SCHEDULE_CRON`, `BACKUP_RETENTION_DAYS`, `BACKUP_STORAGE_PATH` or object-storage credentials if backups are shipped off-host, which they should be — a backup stored only on the same host as the data it backs up is not a real disaster-recovery capability).
**8. Public interfaces:**
```python
def run_postgres_backup() -> BackupResult: ...
def verify_redis_snapshot() -> SnapshotVerificationResult: ...
def run_restore_drill(backup_id: str, target: Literal["scratch_db"]) -> RestoreDrillResult: ...
```
**9. Internal classes:** `BackupResult(backup_id, size_bytes, duration_ms, checksum)`, `RestoreDrillResult(success, row_counts_match, duration_ms, discrepancies)` — the restore drill's job is specifically to compare row counts (and ideally a sampled checksum) between the source and the restored scratch database, so "the restore succeeded" means something concrete and checkable, not just "the command exited zero."
**10. Data flow:**
```
Scheduler (nightly) → enqueue run_postgres_backup
Worker → pg_dump → compress → checksum → ship to configured storage → record BackupResult
Scheduler (monthly) → enqueue run_restore_drill(latest backup_id)
Worker → restore into a scratch database → compare row counts/checksums against source → record RestoreDrillResult → alert (via M3) on any discrepancy or drill failure
```
**11. Sequence (text):**
```
RQ-Scheduler -> Redis: trigger (nightly)
Worker -> backup_jobs: run_postgres_backup()
backup_jobs -> Postgres: pg_dump
backup_jobs -> Storage: upload compressed dump
backup_jobs -> Postgres (metadata table): record BackupResult
backup_jobs -> metrics: emit(BackupCompleted)

RQ-Scheduler -> Redis: trigger (monthly)
Worker -> backup_jobs: run_restore_drill(latest_backup_id)
backup_jobs -> Storage: download dump
backup_jobs -> Scratch DB: restore
backup_jobs -> Scratch DB vs Source DB: compare row counts, sampled checksums
alt match
  backup_jobs -> metrics: emit(RestoreDrillSucceeded)
else mismatch or failure
  backup_jobs -> alerting: fire critical alert  [M3's evaluator picks this up on next cycle, or this job notifies directly for zero-delay on something this important]
end
```
**12. Database changes:** a small `backup_records` metadata table (backup_id, created_at, size_bytes, checksum, storage_location) and a `restore_drill_records` table (drill results over time — trend visibility matters here: did the drill get slower or start finding discrepancies more often, feeds M9's dashboard).
**13. Redis changes:** none beyond verifying AOF/RDB snapshot integrity (reading Redis's own persistence files, not writing new Redis keys).
**14. API changes:** `GET /api/v1/admin/backups` (list backup/drill history, admin-only) — read-only visibility, no backup-triggering endpoint exposed over HTTP (backups are schedule-driven and admin-CLI-invokable via the worker job directly, deliberately not exposed as a web-triggerable action to reduce attack surface).
**15. Event flow:** `BackupCompleted`/`RestoreDrillSucceeded`/`RestoreDrillFailed` metric events, the last of which should bypass the normal alert-evaluation-cycle delay and notify immediately given its severity (point 11).
**16. Background worker interactions:** the third scheduled job type, exactly following the established ingestion/alerting pattern — no new mechanism invented.
**17. Error handling:** a failed backup attempt must itself be loudly visible (alerted), not just logged and forgotten — a silent backup failure is worse than no backup system, since it creates false confidence.
**18. Logging requirements:** every backup/drill run logged with full timing and result detail.
**19. Metrics to expose:** backup success rate, restore-drill success rate, backup size trend (a rapidly growing backup size might be the first visible signal of the unbounded-growth risks flagged in earlier audits, e.g. Redis checkpoint accumulation, if it were ever to regress).
**20. Security considerations:** backup files contain sensitive data (user records, API key hashes, investigation content) — must be encrypted at rest in whatever storage they're shipped to, and access to that storage must be as tightly scoped as production database access itself; this is stated explicitly because "we have backups" is only a safety net if the backups themselves aren't a second, less-guarded copy of the same sensitive data.
**21. Performance considerations:** `pg_dump` against a live database has a real I/O/lock cost — schedule during low-traffic windows (configurable, not hardcoded to a specific hour, since "low-traffic window" is deployment-specific).
**22. Scalability considerations:** logical (`pg_dump`) backups are adequate at current data volumes; if the database grows large enough that `pg_dump` duration becomes a real operational burden, physical/streaming replication-based backup is the documented future upgrade path — not built now, named as the trigger condition for later.
**23. Testing strategy:** Unit — checksum/comparison logic. Integration — a full backup → restore-drill cycle against a real (test) Postgres instance, asserting the drill correctly detects both a successful match and a deliberately-introduced discrepancy (seed the scratch restore with one wrong row count, assert the drill catches it — proving the verification logic actually verifies something, not just that the restore command ran).
**24. CI impact:** the backup/restore-drill integration test runs in CI against the existing test Postgres container.
**25. Documentation impact:** the three runbooks in `ops/runbooks/` are the primary deliverable of this milestone's documentation — each must be specific and actionable (exact commands, not "restore the database as appropriate"), since a runbook's value is inversely proportional to how much judgment it requires to follow during an actual incident.
**26. Migration strategy:** standard Alembic migrations for the two new metadata tables.
**27. Rollback strategy:** these are additive tables with no dependency from existing code — trivially reversible.
**28. Definition of Done:** the deliberately-introduced-discrepancy test (point 23) passes, and all three runbooks have been dry-run by a human at least once during milestone review (a runbook nobody has ever followed, even once, is not verified — this is a process requirement for Definition of Done, not just a code requirement).
**29. Risks:** off-host backup storage introduces a new external dependency (object storage credentials, availability) — acceptable and necessary, since on-host-only backups don't actually protect against the most common disaster scenarios (host loss, account compromise).
**30. Future extensibility:** the `restore_drill.py` pattern (automated, verified, scheduled) generalizes to any future data store this project adds — the verification approach, not just the specific Postgres/Redis implementation, is the reusable asset.

**Success Criteria:**
- *Verification:* the deliberately-introduced-discrepancy restore-drill test, plus a human dry-run of all three runbooks.
- *Tests required:* as listed in point 23.
- *CI changes:* new integration test added to the existing suite.
- *Audit findings eliminated:* "no backup strategy... no documented rollback procedure... no backup/restore drill" — named directly in the Phase 3 audit's Production Readiness section.
- *Debt intentionally left behind:* logical backups only (no physical/streaming replication) until the documented scale trigger (point 22) is actually reached.

---

### Milestone 7 — Worker Scaling Policy & Resource Configuration

**1. Goal:** Design and implement the *configuration surface* for worker-pool sizing and resource limits — not autoscaling infrastructure, but the policy layer that makes scaling a config change rather than a redesign when it's actually needed.
**2. Why it exists:** named as a future scaling bottleneck (A.3) that isn't urgent yet but is cheap to design correctly now and expensive to retrofit later; explicitly scoped to avoid the premature-infrastructure mistake this project has consistently and correctly avoided elsewhere (no Kafka, no K8s, still true here).
**3. Dependencies:** Milestone 1 (worker/scheduler images must be CI-verified before designing a scaling policy around them, per A.4.3).
**4. Architectural rationale:** this milestone deliberately does *not* build autoscaling — it builds the observable, tunable inputs (queue depth, worker utilization, configured pool size) that a human (or, later, an autoscaler) needs to make a scaling decision. Building the decision-maker itself before there's operational evidence about what triggers should matter would be exactly the premature optimization the design principles warn against.
**5. Repository structure changes:** `workers/scaling_policy.py` (new, §B).
**6. Files to create:** `workers/scaling_policy.py`, `tests/test_scaling_policy.py`.
**7. Files to modify:** `docker-compose.yml` (explicit resource limits — `mem_limit`, `cpus` — on `app`, `worker`, `scheduler`, previously unset), `config/settings.py` (`WORKER_POOL_SIZE`, `WORKER_CONCURRENCY_PER_PROCESS`), `metrics/collector.py` (emit queue-depth and worker-utilization samples alongside existing job metrics).
**8. Public interfaces:**
```python
def recommended_pool_size(current_queue_depth: int, avg_job_duration_s: float, target_max_wait_s: float) -> int: ...
```
A pure, deterministic recommendation function — deliberately *advisory*, surfaced on the admin dashboard (M9) for a human to act on, not wired to automatically resize anything. This is the concrete expression of "config surface, not autoscaling infrastructure."
**9. Internal classes:** none beyond the function above.
**10. Data flow:** `metrics.collector` samples queue depth (from RQ directly) and job durations on an ongoing basis → `recommended_pool_size` is computed on demand (dashboard view or a periodic log line), never automatically acted upon.
**11. Sequence (text):**
```
[continuous] Worker -> metrics.collector: sample queue depth, job duration
Admin -> Dashboard (M9): view current pool size, queue depth, recommended_pool_size()
Admin -> docker-compose.yml / deployment config: manually adjust WORKER_POOL_SIZE
Admin -> Deployment: redeploy with new worker replica count
```
**12. Database changes:** none beyond what M9's metrics already capture (queue depth becomes one more sampled metric, not a new table).
**13. Redis changes:** none — queue depth is read from RQ's existing Redis-backed queue state, not a new structure.
**14. API changes:** the existing `GET /api/v1/admin/metrics` endpoint gains a `queue_depth`/`recommended_pool_size` field — additive.
**15. Event flow:** none new.
**16. Background worker interactions:** this milestone instruments workers, it doesn't change their execution behavior.
**17. Error handling:** none new.
**18. Logging requirements:** periodic (e.g., hourly) log line summarizing current pool size vs. recommendation, so the signal is visible even without opening the dashboard.
**19. Metrics to expose:** `queue_depth`, `worker_utilization_pct`, `recommended_pool_size` — all three, since the recommendation without the inputs that produced it is much less trustworthy to a human operator deciding whether to act on it.
**20. Security considerations:** resource limits (`mem_limit`/`cpus`) are themselves a defense against one class of resource-exhaustion risk (a runaway job consuming unbounded host memory) — worth stating explicitly as a security-adjacent benefit of what might otherwise read as purely an operations concern.
**21. Performance considerations:** this is the milestone that directly addresses the "worker throughput is the first thing that will actually bind" prediction from A.3 — not by solving it outright, but by making it visible and actionable before it's a live incident.
**22. Scalability considerations:** the entire point of this milestone.
**23. Testing strategy:** Unit — `recommended_pool_size`'s formula against known input/output pairs (e.g., high queue depth + long job duration → higher recommendation; low queue depth → recommendation doesn't drop below a configured minimum). Integration — resource limits actually apply and are respected by Docker Compose (a container hitting its configured memory limit is killed/restarted as expected, verified in a test, not just declared in YAML and assumed to work).
**24. CI impact:** none new.
**25. Documentation impact:** `docs/phase4/worker_scaling.md` — explicitly states this is a manual, advisory system today and names the conditions under which building real autoscaling would become justified (mirroring the exact style of every other "not yet, here's the trigger" decision already documented in Architecture v1.0).
**26. Migration strategy:** none.
**27. Rollback strategy:** resource limits can be loosened/removed via config with no code change if they prove too restrictive.
**28. Definition of Done:** the recommendation formula test passes against realistic fixture scenarios; a memory-limited container in a test is demonstrably killed/restarted when it exceeds its configured limit, proving the resource-limit configuration is actually enforced, not just declared.
**29. Risks:** setting resource limits too conservatively could cause legitimate jobs to be killed — mitigate by shipping generous, documented defaults and making them easy to tune, not by skipping limits entirely (unbounded resource usage is a real risk this project hasn't had to think about yet purely because it hasn't hit real load).
**30. Future extensibility:** `recommended_pool_size`'s pure-function design means a future real autoscaler (if genuinely justified later) calls the exact same function this milestone ships — the decision logic doesn't need to be rebuilt, only the automation wrapping it.

**Success Criteria:**
- *Verification:* the memory-limit-enforcement test in point 28.
- *Tests required:* recommendation-formula unit tests, resource-limit-enforcement integration test.
- *CI changes:* none.
- *Audit findings eliminated:* "no worker-scaling policy" (A.2.6, newly named in this document, not from a prior audit, since it wasn't urgent enough to flag as a defect before — correctly treated as a proactive improvement, not a bug fix).
- *Debt intentionally left behind:* no automatic autoscaling — explicitly, permanently deferred until real operational evidence justifies it, not a temporary gap.

---

### Milestone 8 — Agent Contribution Framework

**1. Goal:** A documented, tooling-enforced pattern for adding a new domain agent — a copyable scaffold plus a CI check that validates a new agent conforms to the `AgentInput`/`AgentOutput` contract — making this genuinely accessible to an external open-source contributor, not just to someone who already read all six existing agents.
**2. Why it exists:** named in A.2.7 as a real barrier to this project succeeding as "a serious long-term open-source platform" — the contract already exists and is good (Phase 2 built it carefully); what's missing is a documented, discoverable, enforced path to using it.
**3. Dependencies:** Milestone 4 (Evidence/citation-ID schema must be finalized before this milestone documents/scaffolds the contract, per A.4.1) — this is the one hard cross-track dependency in Phase 4 that must not be skipped.
**4. Architectural rationale:** this is deliberately **not** a dynamic plugin-loading system — new agents are still added by writing code and registering them in `orchestrator/agents/registry.py`, exactly as established since Phase 2. Building a dynamic loader now would be exactly the kind of premature, speculative infrastructure this project's Architecture v1.0 has correctly rejected every time it came up (Kafka, K8s, multi-tenancy). What's added here is contributor *tooling and enforcement* around the existing, static pattern — a meaningfully different, much smaller, much better-justified thing.
**5. Repository structure changes:** `docs/CONTRIBUTING_AGENTS.md`, `scripts/new_agent_template/` (both new, §B).
**6. Files to create:** `docs/CONTRIBUTING_AGENTS.md`, `scripts/new_agent_template/{__init__.py.template,agent.py.template,test_agent.py.template}`, `scripts/scaffold_new_agent.py` (a small CLI: `python scripts/scaffold_new_agent.py my_new_domain` generates a correctly-shaped, registry-registered, test-stubbed starting point), `.github/workflows/agent_contract_check.yml` (a CI job that imports every registered agent and asserts its `run()` function's signature matches `AgentInput -> AgentOutput` — a structural, automated contract check, not just a documentation promise).
**7. Files to modify:** `orchestrator/agents/registry.py` (if needed, to support the contract-check tooling introspecting it), `README.md` (a "Contributing a new domain agent" section pointing to the new guide — folding naturally into M10's broader README overhaul, sequenced so M10 doesn't have to reinvent this).
**8. Public interfaces:** `scripts/scaffold_new_agent.py <domain_name>` (CLI, not a Python API — this is contributor tooling, not application code).
**9. Internal classes:** an `AgentContractValidator` used by the new CI job — inspects the registry, checks each agent's callable signature and return-type annotation against `AgentInput`/`AgentOutput`, and (a further, non-obvious but valuable check) asserts every agent has a corresponding entry in the eval benchmark set's `expected_domains` coverage from Phase 3's Milestone 5 — closing the loop between "a new agent exists" and "the eval harness actually knows to test it," which is exactly the kind of thing that's easy for a well-meaning contributor to miss and easy for automated tooling to catch.
**10. Data flow:** `CI job → import orchestrator.agents.registry → for each registered agent: inspect signature → assert conformance → assert eval-benchmark coverage exists → pass/fail`.
**11. Sequence (text):**
```
Contributor -> scaffold_new_agent.py: run("volcanic_activity")
scaffold_new_agent.py -> filesystem: generate orchestrator/agents/volcanic_activity/{agent.py, __init__.py}
scaffold_new_agent.py -> filesystem: generate tests/test_volcanic_activity_agent.py
scaffold_new_agent.py -> registry.py: add registration line [or print instructions if auto-editing the registry is judged too invasive]
Contributor -> implements agent logic
Contributor -> opens PR
CI -> agent_contract_check: import registry, validate every agent's signature
CI -> agent_contract_check: check eval/benchmarks/questions.json for volcanic_activity coverage
alt missing eval coverage
  CI -> fail: "new agent 'volcanic_activity' has no benchmark question — add one to eval/benchmarks/questions.json"
else
  CI -> pass
end
```
**12. Database changes:** none.
**13. Redis changes:** none.
**14. API changes:** none directly, though a new agent may eventually need new domain-specific external tool credentials in `Settings` — documented in the contribution guide as part of the checklist, not a schema change this milestone makes itself.
**15. Event flow:** none new.
**16. Background worker interactions:** none new.
**17. Error handling:** the contract-check CI job must produce a specific, actionable failure message (point 11's example) — a generic "contract check failed" is much less useful to a first-time external contributor than a message naming exactly what's missing and where.
**18. Logging requirements:** none new (this is CI/dev tooling, not runtime application behavior).
**19. Metrics to expose:** none new.
**20. Security considerations:** the scaffold CLI generates code from templates with no external input beyond a domain name used for file/class naming — sanitize that name (alphanumeric + underscore only) to avoid any path-traversal-via-domain-name mistake in the generator itself, however unlikely; cheap to guard against, worth naming explicitly rather than assuming it away.
**21. Performance considerations:** none — dev-time tooling only.
**22. Scalability considerations:** this milestone is itself the answer to the "contributor growth" scaling dimension named in A.3.
**23. Testing strategy:** Unit — `AgentContractValidator` against a deliberately-non-conforming fixture agent (wrong signature), asserting it's correctly caught. Integration — running `scaffold_new_agent.py` end-to-end and asserting the generated code passes the contract check immediately, unmodified (proving the template itself is correct, not just that the checker works). Failure-path — a new agent registered with no corresponding eval-benchmark question → CI fails with the specific message from point 11.
**24. CI impact:** new `agent_contract_check.yml` workflow.
**25. Documentation impact:** `docs/CONTRIBUTING_AGENTS.md` is the primary deliverable — must be usable by someone who has read `Architecture.md` but none of the existing agent source code, which is the actual bar for "open-source contributor ready," not "an engineer already on the team can figure it out."
**26. Migration strategy:** none.
**27. Rollback strategy:** none needed — additive tooling and documentation only.
**28. Definition of Done:** a person unfamiliar with the codebase's internals (in practice: reviewed by someone on the team deliberately trying to follow only the written guide, not their existing knowledge) can generate, implement, and pass CI for a trivial new agent using only `CONTRIBUTING_AGENTS.md` and the scaffold tool.
**29. Risks:** documentation rot — this guide must be kept current as the agent contract evolves; mitigate by having the contract-check CI job itself fail loudly if the registry's actual shape diverges from what the template generates, turning "the docs are stale" into a CI-visible fact rather than a silent decay.
**30. Future extensibility:** this is explicitly the foundation for future community-contributed domain agents without requiring a dynamic plugin system — if demand for even-lower-friction contribution ever justifies one, the contract this milestone formalizes is exactly what such a system would need to validate against, so this work isn't wasted even in that hypothetical future.

**Success Criteria:**
- *Verification:* the "unfamiliar reviewer" dry-run in point 28.
- *Tests required:* contract-validator unit tests, scaffold-generates-passing-code integration test, missing-eval-coverage failure-path test.
- *CI changes:* new `agent_contract_check.yml` workflow.
- *Audit findings eliminated:* A.2.7 (no documented/enforced contribution path) — a proactive fix, not a prior-audit-named defect.
- *Debt intentionally left behind:* still no dynamic plugin loading — explicitly, permanently, by design, not a gap.

---

### Milestone 9 — Admin Observability Dashboard

**1. Goal:** A real web frontend (`admin_ui/`) surfacing metrics (Phase 3 M9), alerts and incident history (Phase 4 M3), and worker-scaling recommendations (Phase 4 M7) — the first genuine UI in this project's history.
**2. Why it exists:** explicitly deferred twice already (Phase 3's M9 design doc and the Phase 3 audit both named "a real dashboard UI... is legitimately separate, larger-scoped work") — Phase 4 is the right time specifically because the three things worth putting on a dashboard (metrics, alerts, scaling signal) now all exist to show.
**3. Dependencies:** Milestone 3 (alerting) and Milestone 7 (scaling policy) — sequenced after both per A.4.2, so the dashboard is built once, showing everything worth showing, rather than being extended immediately after shipping.
**4. Architectural rationale:** `admin_ui/` is a fully separate deployable (its own `Dockerfile.admin_ui`, its own `package.json`) that consumes the existing `/api/v1/admin/*` HTTP surface exactly like any external client — it does not import Python code, does not share a deployment unit with `app`/`worker`, and does not get special backend access. This is a deliberate test of Phase 3's API-versioning discipline (Milestone 10): if the dashboard needs backend changes to consume the API reasonably, that's a signal the API wasn't as externally-usable as claimed; if it doesn't, that's real validation.
**5. Repository structure changes:** `admin_ui/` (new top-level directory, §B).
**6. Files to create:** `admin_ui/package.json`, `admin_ui/src/pages/{Metrics,Alerts,Investigations,Workers}.tsx`, `admin_ui/src/api/client.ts`, `admin_ui/Dockerfile.admin_ui`, `admin_ui/tests/` (component tests), `.github/workflows/admin_ui_ci.yml` (a separate, independent CI job — Node/TypeScript tooling, not mixed into the Python `ci.yml`).
**7. Files to modify:** `docker-compose.yml` (new `admin_ui` service, a fourth deployable alongside `app`/`worker`/`scheduler`), `gateway/middleware.py` composition (no change needed if the dashboard authenticates as a normal `admin`-role JWT user through the existing login flow — deliberately not building a separate admin-auth mechanism, reusing Milestone 1-of-Phase-3's role model exactly as designed for this).
**8. Public interfaces:** none new on the backend — the dashboard is purely a consumer of `GET /api/v1/admin/metrics`, `GET /api/v1/admin/alerts`, `GET /api/v1/admin/backups` (M6), and the `recommended_pool_size` field added to metrics (M7).
**9. Internal classes:** none backend-side; frontend-side, a thin typed API client (`admin_ui/src/api/client.ts`) generated from (or manually kept in sync with, whichever the implementer finds lower-friction) the OpenAPI spec M10 publishes — noted as a natural pairing with M10, not a hard dependency, since the dashboard can be built against the existing hand-typed endpoints regardless of whether M10 has landed yet.
**10. Data flow:** `Admin logs in via existing JWT flow → Dashboard polls/fetches admin endpoints on a refresh interval → renders metrics/alerts/scaling recommendation`.
**11. Sequence (text):**
```
Admin -> Dashboard: navigate to /alerts
Dashboard -> API: GET /api/v1/admin/alerts  [Authorization: Bearer <jwt>]
API -> RequireRole(ADMIN): check
API -> Postgres: SELECT alert_incidents ...
API -> Dashboard: 200 {incidents: [...]}
Dashboard -> Admin: render incident list, firing/resolved status
```
**12. Database changes:** none — read-only consumer of existing tables.
**13. Redis changes:** none.
**14. API changes:** none required beyond what M3/M6/M7 already added — if the dashboard's needs reveal a genuinely missing endpoint during implementation, that's a small, additive fix to the admin API surface, not a redesign.
**15. Event flow:** optionally, the dashboard could use SSE (reusing Phase 2's existing streaming infrastructure) for a live-updating alerts feed rather than polling — a reasonable enhancement, not required for Definition of Done, since polling is simpler and adequate for an admin-facing tool used by a small number of operators, not end users at scale.
**16. Background worker interactions:** none — the dashboard never talks to workers directly, only through the API, preserving the trust-boundary discipline established since Phase 1.
**17. Error handling:** the dashboard must handle the API being unreachable gracefully (a clear "cannot reach GaiaOS API" state, not a blank page or an unhandled exception) — basic frontend hygiene, worth stating since it's exactly the kind of thing that's easy to skip when a UI is "just for us."
**18. Logging requirements:** none new backend-side; frontend error logging (e.g., to the browser console, optionally to a lightweight frontend error-reporting hook) is a reasonable addition but not specified in detail here, since it's genuinely a smaller decision than everything else in this milestone.
**19. Metrics to expose:** none new — the dashboard displays existing metrics, it doesn't generate new ones about itself (a "metrics about the metrics dashboard" would be over-engineering for an internal admin tool).
**20. Security considerations:** the dashboard must never expose non-admin data or accept unauthenticated requests — it inherits this correctly by construction, since it only ever calls already-`RequireRole(ADMIN)`-gated endpoints; no new backend security surface is introduced, which is precisely why building it now (after auth/RBAC matured in Phase 3) rather than earlier was the right sequencing call.
**21. Performance considerations:** a polling interval that's too aggressive could itself become unnecessary load on the admin API — a sensible default (e.g., 30–60 second refresh) documented and configurable, not hardcoded to an arbitrarily tight interval.
**22. Scalability considerations:** an admin dashboard's traffic is bounded by the number of operators, not by end-user query volume — explicitly not a scalability concern in the same sense as the rest of this document.
**23. Testing strategy:** frontend component tests (does the metrics page render given a fixture API response, does the alerts page correctly distinguish firing vs. resolved), an integration test that runs the dashboard against a real (test) instance of the backend and asserts the login → view-metrics flow works end-to-end, and an explicit test of the "API unreachable" graceful-failure state from point 17.
**24. CI impact:** a new, independent CI workflow for the Node/TypeScript project — deliberately not mixed into the existing Python `ci.yml`, since the two toolchains have nothing in common and forcing them into one workflow would only slow down every Python-only PR's CI feedback loop.
**25. Documentation impact:** `docs/phase4/admin_dashboard.md`, plus a `admin_ui/README.md` for frontend-specific setup instructions (separate from the root README, since a Python backend contributor and a frontend contributor have almost entirely non-overlapping setup needs).
**26. Migration strategy:** none.
**27. Rollback strategy:** the `admin_ui` service can be stopped/removed independently with zero effect on the rest of the system — this is the direct benefit of it being a fully separate deployable rather than bolted into `app`.
**28. Definition of Done:** an admin user can log in, view current metrics, view alert incident history (including a deliberately-seeded firing/resolved pair), and see a worker-scaling recommendation, all through the deployed dashboard rather than raw API calls.
**29. Risks:** this is the first frontend/Node work in a previously Python-only repository — the main risk is tooling/CI-integration friction (a new language ecosystem in the repo), mitigated by keeping it a fully separate, independently-deployable, independently-tested project from day one rather than trying to share build tooling with the Python side.
**30. Future extensibility:** once this exists, it's the natural home for anything else Phase 5+ wants to surface to operators (e.g., a future manual-trigger UI for backup/restore-drill runs, currently deliberately not web-triggerable per M6's security rationale — revisiting that decision, if ever, would extend this dashboard, not require a new one).

**Success Criteria:**
- *Verification:* the end-to-end login→metrics→alerts→scaling-recommendation flow in point 28.
- *Tests required:* frontend component tests, backend-integration end-to-end test, API-unreachable graceful-failure test.
- *CI changes:* new, independent `admin_ui_ci.yml` workflow.
- *Audit findings eliminated:* the twice-deferred "no dashboard UI" gap, now closed with its actual prerequisites (alerting, scaling signal) in place rather than built prematurely.
- *Debt intentionally left behind:* polling instead of SSE for live updates — an explicit, reasonable simplification for an internal admin tool, not an oversight.

---

### Milestone 10 — Public Documentation, API Spec Publishing & README Overhaul

**1. Goal:** Publish a generated (not hand-maintained) OpenAPI spec; fully rewrite the README's status table to reflect the actual, current state of Phases 1–4; consolidate contributor-facing documentation (linking M8's agent guide, `ops/runbooks/`, and the new admin dashboard docs) into a coherent entry point.
**2. Why it exists:** the README staleness finding has now been raised and left unfixed across three consecutive audits (Part 1 of this document) — this is the phase where it finally gets fixed, deliberately last, so it can accurately describe everything else Phase 4 built rather than needing yet another revision immediately after.
**3. Dependencies:** effectively all other Phase 4 milestones, since this milestone's job is to accurately document their outcomes — sequenced last for exactly that reason, not because it's low-value, but because writing it any earlier would mean rewriting it again immediately.
**4. Architectural rationale:** the OpenAPI spec is generated from FastAPI's existing automatic schema (`app.openapi()`), not hand-authored — a hand-maintained spec drifts from the real API the same way the README drifted from real project status; generating it mechanically is the structural fix that prevents this specific category of staleness from recurring for the API spec the way it did for the README.
**5. Repository structure changes:** `docs/api/openapi/` (new, §B).
**6. Files to create:** `scripts/generate_openapi_spec.py` (calls `app.openapi()`, writes the result to `docs/api/openapi/openapi.json`, run in CI to detect drift — see point 24), `docs/api/CHANGELOG.md` (already established in Phase 3's Milestone 10 — this milestone ensures it's actually current, not a new file).
**7. Files to modify:** `README.md` (complete status-table rewrite covering all four phases' actual milestones, a "Contributing" section linking `CONTRIBUTING_AGENTS.md`, an "Operations" section linking `ops/runbooks/`), `.github/workflows/ci.yml` (add an OpenAPI-spec-drift check: regenerate the spec, diff against the committed version, fail if they differ and weren't updated together — the same "make staleness structurally impossible, not just discouraged" principle applied to the README problem, applied here proactively before it becomes its own three-audit-old finding).
**8. Public interfaces:** none new — this milestone publishes and documents existing interfaces, it doesn't add any.
**9. Internal classes:** none new.
**10. Data flow:** `CI → generate_openapi_spec.py → compare against committed docs/api/openapi/openapi.json → pass if identical, fail with a clear "spec is out of date, regenerate and commit" message if not`.
**11. Sequence (text):**
```
Developer -> FastAPI app: adds/modifies a route
Developer -> commits code, forgets to regenerate the spec
CI -> generate_openapi_spec.py: regenerate
CI -> diff: committed spec vs regenerated spec
alt differ
  CI -> fail: "OpenAPI spec is stale — run scripts/generate_openapi_spec.py and commit the result"
else
  CI -> pass
end
```
**12. Database changes:** none.
**13. Redis changes:** none.
**14. API changes:** none — this milestone documents the API, it doesn't change it.
**15. Event flow:** none.
**16. Background worker interactions:** none.
**17. Error handling:** none new (this is docs/CI tooling).
**18. Logging requirements:** none new.
**19. Metrics to expose:** none new.
**20. Security considerations:** review the generated OpenAPI spec for accidental over-disclosure (e.g., internal-only fields leaking into the public schema, or the `/internal/smoke-job` endpoint from Milestone 1 appearing in a published spec meant for external consumers) — a concrete, specific check, not a vague "review for security," since the smoke-job endpoint is a real, named thing that must not end up in a document meant to help external API consumers.
**21. Performance considerations:** none.
**22. Scalability considerations:** none.
**23. Testing strategy:** the CI drift-check itself (point 11) is the primary test — additionally, a test asserting the internal-only smoke-job endpoint is excluded from the published spec (point 20), proving the security review in point 20 is enforced, not just performed once and hoped to remain true.
**24. CI impact:** new OpenAPI-drift-check step in `ci.yml`.
**25. Documentation impact:** this milestone *is* the documentation impact — the README rewrite, the published spec, and the contributor-documentation consolidation are its entire deliverable.
**26. Migration strategy:** none.
**27. Rollback strategy:** none needed.
**28. Definition of Done:** the README accurately lists all Phase 1–4 milestones (verified against `git log`, not against memory or assumption — the same standard this audit itself has applied throughout); the OpenAPI spec is published, generated (not hand-written), and the drift-check test proves it stays that way; the internal smoke-job endpoint is confirmed absent from the published spec.
**29. Risks:** none significant — this is the lowest-risk milestone in Phase 4, appropriately, since it's the one most purely about closing out accumulated debt rather than adding new capability.
**30. Future extensibility:** the drift-check pattern (generate, diff, fail on mismatch) is the template for keeping any future generated-documentation artifact honest — worth naming as a reusable pattern, not just a one-off fix for the OpenAPI spec specifically.

**Success Criteria:**
- *Verification:* README accuracy checked against `git log` directly; OpenAPI drift-check test; smoke-endpoint-exclusion test.
- *Tests required:* the two CI-level tests named in point 23.
- *CI changes:* new OpenAPI-drift-check step.
- *Audit findings eliminated:* the three-audits-old README staleness finding, finally, and proactively prevents the equivalent finding from ever applying to the OpenAPI spec.
- *Debt intentionally left behind:* none — this milestone exists specifically to leave zero known documentation debt behind it.

---

## Part D — After All Milestones

### D.1 Overall Phase 4 Architecture
Phase 4 adds four new cross-cutting infrastructure layers (`alerting/`, `ops/`, `admin_ui/`, contributor tooling in `scripts/`) on top of an unchanged Phase 1–3 core. None of them touch the graph/agent/schema architecture's shape (M4's `Evidence.id` addition is the only schema change, and it's additive, non-breaking, and explicitly designed to be so). The project's established idioms — Protocol-based interfaces (auth, rate limiting, now notification channels), the scheduler-based worker-job pattern (ingestion, now alerting and backups), and the "typed config surface over hardcoded values" discipline — are each reused a further time in Phase 4 rather than reinvented, which is itself evidence the Phase 1–3 architecture was built with enough foresight to absorb a fourth phase without strain.

### D.2 Dependency Graph Between Milestones
```
Trust & Safety track:              Product Maturity track:
M1 (CI/Deployment Integrity)        M4 (Citation IDs)
  │                                   │
M2 (Auth Security Review)             │ [must precede M8]
                                       │
M6 (Backup/DR) [no dependencies]     M5 (Geocoding/HTTP client) [no dependencies]
                                       │
                                     M3 (Alerting) [depends on Phase 3's metrics, already done]
                                       │
                                     M7 (Worker Scaling) [depends on M1]
                                       │
                                     M8 (Agent Contribution Framework) [depends on M4]
                                       │
                                     M9 (Admin Dashboard) [depends on M3 + M7]
                                       │
                                     M10 (Docs/README/OpenAPI) [depends on all of the above, sequenced last]
```
M2 and M6 have zero dependencies on anything else in Phase 4 and can be done in any order, in parallel with the entire Product Maturity track. M4 and M5 have zero dependencies on each other or on the Trust & Safety track and can also run in parallel with it.

### D.3 Critical Implementation Order
For a single engineer: **M1 → M2 → M4 → M5 → M6 → M3 → M7 → M8 → M9 → M10.** This interleaves the two tracks (safety-critical items first, then the product-maturity spine in its required order) rather than finishing one track fully before starting the other, since M1 (CI integrity) is the one item genuinely worth doing before anything else touches workers, but M2/M6 don't need to block the Product Maturity track from starting.
For two engineers: one takes M1 → M6 → M2 (Trust & Safety), the other takes M4 → M5 → M3 → M7 → M8 → M9 → M10 (Product Maturity), converging only at M10, which genuinely needs everything else done first.

### D.4 Risks If Milestones Are Implemented Out of Order
- **M8 before M4:** the contribution framework documents/scaffolds a citation contract that's about to change — new contributors would learn the old, soon-obsolete pattern. This is the one ordering violation with a real, named cost (A.4.1), not a hypothetical.
- **M9 before M3 or M7:** the dashboard ships with nothing meaningful to show on its two most valuable panels, requiring an immediate follow-up rework rather than a clean build — wasted effort, not a correctness risk, but real waste.
- **M7 before M1:** designing a scaling policy around worker images that were never proven to build correctly in CI is designing on an unverified foundation — low probability of an actual defect (the images do appear correct on inspection, per Part 2 of the prior audit), but poor engineering discipline to build on an assumption when the verification is this cheap to do first.
- **M10 before anything else:** would produce documentation that's immediately wrong the moment the next milestone lands — the exact failure mode this milestone exists to permanently fix, so building it first would be self-defeating.

### D.5 New Technical Debt Introduced (If Any)
- **M4's retained text-matching fallback path** is a deliberate, named, evidence-gated piece of debt (removed only once real fallback-rate data justifies it) — not an oversight, stated as debt because it is genuinely a second code path to maintain until then.
- **M6's logical-backup-only approach** (no physical/streaming replication) is named, scale-gated debt, exactly like every other "not yet, here's the trigger" decision in this project's history.
- **M9's polling-not-SSE dashboard updates** is a small, explicitly reasonable simplification, arguably not real debt at all given the admin-only, low-traffic nature of the consumer, but named for completeness.
- **No new debt is introduced by M1, M2, M3, M5, M7, M8, or M10** — each of those either closes existing debt or adds infrastructure with no known shortcuts taken.

### D.6 Future Phase 5 Prerequisites
- A real Neo4j migration remains gated on the same scale trigger named since Phase 2 — not touched by Phase 4, still correctly deferred.
- Physical/streaming-replication backups become relevant once M6's logical-backup duration becomes an operational burden — the trigger condition is named in M6 itself, not invented fresh here.
- Real worker autoscaling (versus M7's advisory recommendation) becomes justified once `queue_depth`/`recommended_pool_size` data from M7 shows a genuine, recurring need — Phase 5 should look at that data before deciding, not before it exists.
- Multi-tenant organizational data isolation remains excluded, still correctly, absent a new, concrete reason — restated here for the fourth consecutive phase specifically to make clear this isn't an oversight, it's a standing, reviewed decision.
- If `admin_ui/` proves out the frontend-toolchain investment, a future *user-facing* (not just admin) UI becomes a much lower-risk proposition for Phase 5, since the tooling/CI/deployment pattern will already be proven.

### D.7 Updated Engineering Roadmap (Summary)
Phase 1: foundation. Phase 2: reasoning core. Phase 3: trust infrastructure (identity, durability, correctness). Phase 4: operational maturity and open-source readiness (alerting, backup/DR, contribution tooling, dashboard, documentation integrity). The through-line across all four phases is consistent: build the smallest correct thing the current, real requirement justifies, verify it with real tests and real audits, and defer everything else with a named, honest trigger condition rather than either over-building preemptively or leaving a silent gap. Phase 4 doesn't change that discipline; it applies it to a new category of concern (operations and contributor experience) rather than to new reasoning capability, which is exactly the right next step for a system whose reasoning core was already sound going in.

---

## Part E — Phase 4 Exit Criteria, Audit Checklist, and Production Readiness Criteria

### E.1 Phase 4 Exit Criteria
- All ten milestones' Definitions of Done (Part C) are met and independently verified, not self-reported.
- CI builds and smoke-tests all four deployables (`app`, `worker`, `scheduler`, `admin_ui`).
- The full security checklist from Milestone 2 passes as automated tests, with written findings on record.
- At least one full, human-witnessed restore drill (Milestone 6) has been performed, not just automated and assumed correct.
- The README accurately reflects `git log` reality (Milestone 10) — checked directly, not assumed.
- No Critical or High finding remains open from this document's own eventual closing audit (see E.2) without an explicit, named, accepted-risk justification.

### E.2 Engineering Audit Checklist for Phase 4 Completion
1. Re-verify every Part 1-style "previous finding" table entry from the prior three audits — confirm nothing regressed.
2. Independently trigger the CI worker/scheduler smoke test with a deliberately-broken image, confirming M1's Definition of Done still holds (not just at merge time, but at audit time).
3. Independently attempt the password-reset flow's non-enumeration and rate-limiting properties (M2) with adversarial test cases, not just the milestone's own test suite.
4. Trigger at least one real alert (M3) via a seeded metric condition and confirm the full firing→resolution lifecycle, including the actual notification arriving at a real (test) webhook endpoint.
5. Confirm the citation-ID migration (M4) via a real Synthesis run against real evidence, not just unit-level schema checks.
6. Confirm dynamic station lookup (M5) against at least 3 real, non-cached cities with known-correct expected stations.
7. Independently run the restore drill (M6) against a genuinely separate scratch environment, not the same database instance under a different name.
8. Confirm resource limits (M7) are actually enforced by attempting to exceed them in a controlled test, not just reading the Compose YAML.
9. Have someone genuinely unfamiliar with the codebase attempt the agent-contribution flow (M8) using only the published guide.
10. Log in to the deployed admin dashboard (M9) as a real admin user and confirm all four panels (metrics, alerts, backups, scaling) render real data.
11. Confirm the OpenAPI drift-check (M10) actually fails when a route is changed without regenerating the spec — don't just trust that it would.

### E.3 Production Readiness Criteria After Phase 4
GaiaOS should be considered genuinely production-ready — not just "the code is good," but operationally ready for real users and real incidents — only once **all** of the following hold simultaneously:
- A real incident can be detected (M3) without a human noticing symptoms first.
- A real incident can be diagnosed using the admin dashboard (M9) without needing to read raw logs or query the database by hand.
- A real data-loss scenario can be recovered from using a runbook (M6) that has actually been executed successfully at least once outside of an emergency.
- A new contributor can add a capability (M8) without requiring a core team member's direct, code-level guidance.
- The system's own documentation (M10) can be trusted as an accurate description of its current state, verified by a mechanism that fails loudly on drift rather than one that relies on someone remembering to update it.

If all five hold, GaiaOS has crossed from "well-engineered software" to "an operable system" — a distinction this document has drawn explicitly throughout, because the two are not the same claim, and conflating them is exactly how well-built systems end up being operationally fragile in practice.
