# GaiaOS — Phase 8 Roadmap: Multi-Node Governance & Finish-Line Hardening

**Role:** Principal Software Architect / Senior OSS Maintainer / Technical Mentor
**Baseline:** Phases 1–7 complete, frozen at v0.7.3, seven independent engineering audits performed across this engagement, all findings from the Phase 7 audit (documentation currency, GitHub publication gap, Prometheus token comparison, persisted scaling telemetry) resolved as part of Phase 7's closure per the current brief's own stated context.
**Planning only.** No code, commits, branches, tags, or releases are created by this document.

---

## Repository Review Summary (What Already Exists — Not to Be Duplicated)

- **Reasoning:** LangGraph orchestration, six domain agents, Adaptive Planner, Synthesis/Critic with structural citation validation and stable IDs, bounded Critic replan loop, Multi-Agent Collaboration Bus, Cross-Domain Synthesis, Agent Plugin Architecture, explainability trace exploration, longitudinal pattern mining.
- **Evidence & Data:** Hybrid retrieval, real literature corpus, PostGIS + OSM boundaries, eight real environmental data sources, resilience layer (retry/circuit-breaker/degraded-mode) wrapping all of them, calibrated simulation models.
- **Platform:** JWT + API key auth, RBAC, Redis rate limiting, durable checkpointed workers, single-node advisory scaling policy **now with persisted telemetry (Phase 7)**, OpenMetrics/Prometheus-scrapeable endpoint with hardened auth (Phase 7), SLO/error-budget alerting.
- **Ecosystem:** Python SDK (generated, drift-checked), CLI Wizard, public research API, optional MinIO storage backend.
- **Governance:** LICENSE, CODE_OF_CONDUCT, SECURITY.md, issue/PR templates, `Audit_Index.md`, full contributor onboarding docs, documentation-drift CI protection (Phase 7).
- **Twice evaluated, both times evidence-negative:** multi-node worker deployment (Phase 5 M7, Phase 7 M5) — real, sound, quantitative trigger conditions defined (queue depth, sustained utilization, P95 wait) but never crossed.
- **Still genuinely open, correctly deprioritized until now:** dependency vulnerability scanning, SBOM, image-digest pinning, GitHub Actions SHA-pinning, a formal API stability/deprecation policy, automated release publishing.

**What this review rules out for Phase 8:** a third manual "should we scale yet" evaluation milestone (§ADR-801 explains why), any new domain-agent or reasoning capability (nothing in this phase's mission calls for it), any mandatory Kubernetes production path (still unjustified by evidence), any multi-tenant/organizational data model (excluded for the seventh consecutive phase).

---

## GaiaOS Finish-Line Assessment

*(Full detail in the standalone `finish_line_assessment.md`; summarized here because it directly determines this roadmap's shape.)*

**Recommendation: Phase 8 is the final major engineering phase.** After Phase 8's capstone milestone, GaiaOS should cut v1.0.0. No Phase 9 is recommended. The evidence: every remaining gap identified across seven audits is either (a) already closed, (b) small, bounded, security/release-hygiene work appropriate for a "harden before v1.0" phase, or (c) explicitly, correctly not needed yet (multi-node production infrastructure). None of the remaining work is exploratory, speculative, or feature-shaped — it is entirely "complete → harden → verify → release" work, exactly the mode the brief asks Phase 8 to prefer over indefinite feature addition.

---

## Architecture Decision Records

### ADR-801: No Third Manual Multi-Node Evaluation Milestone — Event-Driven Re-Evaluation Instead

**Decision:** Phase 8 does not repeat Phase 5 M7 / Phase 7 M5's manual evidence-review exercise a third time. Instead, it wires the already-defined, already-sound quantitative triggers (queue depth, sustained worker utilization, P95 queue wait) directly into the existing alerting system (Phase 4 M3 / Phase 5 M8), so a future scaling decision is triggered by the system itself crossing a real threshold, not by a calendar date or a new phase starting.
**Context:** two independent, rigorous evaluations have already reached the same conclusion (no multi-node need yet). A third manual review, absent new evidence, would be process theater — exactly the "milestone theater" the Phase 7 audit was asked to watch for, now being proactively avoided rather than committed.
**Alternatives considered:** re-running the M5 evaluation methodology once more (rejected — no reason to expect a different result without new data); ignoring the question entirely until someone notices a problem (rejected — this is the reactive failure mode good alerting exists to prevent).
**Why this wins:** it converts a recurring manual chore into a permanent, load-bearing piece of infrastructure the project already has (alerting) — the same "reuse, don't duplicate" discipline this project has applied in every prior phase, applied here to a *process*, not just a *component*.
**Future implications:** if the alert never fires, that is itself the ongoing, continuously-updated answer to "is multi-node needed yet" — no future audit needs to re-ask this question from scratch; it needs only to check whether the alert has ever fired.

### ADR-802: Kubernetes Remains Optional, Dev-Verified Only, Never a Production Default

**Decision:** Phase 8 builds a documented, CI-verified, dev-only k3s deployment path (Helm chart + smoke test), explicitly and permanently subordinate to Docker Compose, which remains the default, recommended, student-first path.
**Context:** the Phase 7 audit's Rejected Refinement Audit identified this specific narrow scope (dev-only smoke test, not a production claim) as the one place where "wait for evidence" and "prepare cheaply while waiting" weren't in tension.
**Alternatives considered:** full production Kubernetes support with HPA/multi-cluster tooling (rejected — no evidence justifies this, and building it would violate the free-first/student-first non-negotiable); rejecting Kubernetes entirely, even the narrow smoke test (rejected — the Phase 7 audit specifically found this over-conservative given the low cost of the narrow version).
**Why this wins:** delivers exactly the value the narrow version offers (a tested foothold, zero cost imposed on the default path) without overreaching into the production claim the evidence doesn't support.
**Future implications:** if ADR-801's alert ever fires, this milestone's output is the concrete starting point for a future, evidence-justified production Kubernetes path — not wasted work, but explicitly not promoted to "supported production deployment" until that happens.

### ADR-803: v1.0 Means an API Stability Promise, Not a Feature Threshold

**Decision:** "v1.0" is defined by this roadmap as the point at which GaiaOS makes a formal, written commitment to its public API's backward compatibility — not by any particular feature count or capability level.
**Context:** the project could plausibly call any of the last three phases "v1.0-worthy" by feature count; the actual gating question for a real platform's 1.0 is whether external consumers (now real: the SDK, the CLI, research-API consumers) can trust the contract won't break under them.
**Alternatives considered:** defining v1.0 by feature completeness (rejected — feature count is a weak, essentially arbitrary threshold, and this project has correctly avoided that framing since Architecture v1.0's own original document); an indefinite v0.x series with no 1.0 commitment (rejected — real external consumers now exist and deserve a real stability promise, not permanent beta status).
**Why this wins:** it's the only definition of "done" consistent with what actually matters to the people this roadmap's finish line is for — external contributors, SDK/CLI consumers, and anyone deploying GaiaOS in production.
**Future implications:** post-v1.0, any breaking change requires a `/api/v2` prefix (already-established policy since Phase 4 M10) and a major version bump — this ADR is what makes that policy actually mean something, rather than being a rule that's technically stated but never yet had to be honored under a real stability promise.

---

## Milestone 1 — Automated Scaling-Trigger Alerting

**Purpose:** Turn Phase 5 M7's and Phase 7 M5's quantitative scaling triggers (queue depth, sustained worker utilization, P95 queue wait) from numbers a human has to remember to check into a live, monitored condition the existing alerting system watches continuously.

**Problem being solved:** the project has now twice done real, rigorous manual work to answer "do we need multi-node yet" — and has no mechanism to notice, between phases, if the answer changes. This is a genuine reliability gap in the project's own decision-making process, not a code gap.

**Why it belongs in Phase 8:** it directly implements ADR-801, and it's the cheapest, highest-leverage way to make sure the (correct) decision not to build multi-node infrastructure yet doesn't quietly become stale.

**Existing architecture reused:** Phase 4 M3's alert-evaluation scheduled job, Phase 5 M8's `AlertRule`/SLO framework, Phase 7's newly-persisted scaling-telemetry table (queue depth/utilization samples over time — the exact data source this milestone needs, already built).

**Proposed architecture:** three new `AlertRule` entries (one per named trigger), evaluated on the existing alert-evaluation cadence against the existing persisted-telemetry table — no new evaluation mechanism, no new data source, purely new rule definitions plus the wiring to read from telemetry instead of live metrics for this specific rule set (since "sustained" utilization is a time-window property the point-in-time metrics endpoint alone can't express, but the persisted table can).

**Components affected:** `alerting/rules.py`, `config/slo_definitions.yaml` (or equivalent rule-definition surface), `workers/scaling_policy.py` (read path only, no behavior change to the policy itself).

**Dependencies:** none — both prerequisite pieces (persisted telemetry, alerting framework) are already built.

**Implementation order:** (1) define the three rules against real historical persisted-telemetry data to set sane, non-flapping thresholds (reusing the exact numbers Phase 7 M5 already derived, not re-deriving them); (2) wire evaluation; (3) a deliberately-seeded test proving the alert fires correctly if a threshold is (synthetically) crossed.

**Security implications:** none — read-only over existing internal data.

**DevOps implications:** none new — reuses the existing scheduled-job and alerting infrastructure exactly as designed.

**Testing strategy:** unit tests for each rule's threshold logic against known-correct synthetic telemetry sequences; an integration test seeding a synthetic sustained-threshold-breach scenario and asserting the alert fires exactly once (not flapping) and resolves correctly when the condition clears, reusing Phase 5 M8's already-established flapping-suppression test pattern.

**Failure/recovery strategy:** identical to every other alert rule in this system — a failed evaluation cycle doesn't lose state, retries next cycle, matching the existing, proven pattern.

**Documentation required:** `docs/phase8/scaling_alerting.md`, cross-linked from Phase 7's `scaling_evaluation_m5.md` so a future reader finds the live monitoring, not just the historical one-time evaluation.

**OSS/contributor impact:** none directly — internal operational tooling.

**Free/self-hosted verification path:** entirely local — synthetic telemetry seeded in a test database, no external dependency.

**Acceptance criteria:** the seeded-breach integration test passes, demonstrating correct fire-and-resolve behavior without flapping.

**Explicit non-goals:** this milestone does not decide whether to build multi-node infrastructure — it only ensures that decision gets made with fresh evidence whenever it's actually needed, not on an arbitrary phase-boundary schedule.

---

## Milestone 2 — Optional Multi-Node Deployment Capability (Dev-Verified, Non-Default)

**Purpose:** Build the documented, CI-verified, explicitly-optional multi-node deployment path (Helm chart for a k3s target, plus multi-node Docker Compose deployment documentation) that Milestone 1's alert would otherwise leave the project with no ready answer for if it ever fires.

**Problem being solved:** if ADR-801's alert does eventually fire, the project currently has zero tested path to actually deploy beyond one node — meaning the first real scaling need would trigger emergency infrastructure work under pressure, the worst time to do it carefully.

**Why it belongs in Phase 8:** per ADR-802, this is explicitly scoped to the narrow, low-cost version the Phase 7 audit identified as worth doing now — a tested foothold, not a production commitment.

**Existing architecture reused:** all four existing container images (`app`, `worker`, `scheduler`, `admin_ui`) — this milestone packages them, it does not modify them. The worker/checkpoint architecture already proven safe under concurrent load (Phase 5 M7's load test, which found and fixed real event-loop-lifecycle bugs) is the exact thing being deployed across more nodes, not re-architected.

**Proposed architecture:** a `deploy/helm/gaiaos/` chart wrapping the existing images; a `deploy/compose/multi-node.md` reference document for a non-Kubernetes multi-VPS topology (since Kubernetes is optional, and some self-hosters will reasonably want multi-node without adopting K8s at all); a k3s-in-CI smoke test (`helm install` + the same investigation-submit-and-stream verification Phase 1's original Docker Compose CI check established).

**Components affected:** new `deploy/` directory only — no application code changes.

**Dependencies:** none blocking, though conceptually informed by Milestone 1 (this capability is what Milestone 1's alert would point someone toward, if it ever fires).

**Implementation order:** (1) Helm chart authoring against existing images; (2) multi-node Compose reference documentation; (3) k3s-in-CI smoke test, run on the same infrequent cadence as other long-running CI jobs (nightly eval, Phase 5 M7's load test) — not on every PR.

**Security implications:** the chart must not weaken any existing control (secrets remain `Settings`-driven and validated exactly as in single-node deployment; no new default credentials, no new open ports beyond what Compose already exposes) — an explicit, tested requirement, not an assumption.

**DevOps implications:** a new, infrequent CI job; no change to the existing per-PR pipeline's speed or reliability.

**Testing strategy:** the k3s smoke test itself is the primary verification — real `helm install`, real investigation submitted and streamed to completion, proving the K8s path delivers the same correctness the Compose path already guarantees.

**Failure/recovery strategy:** documented, standard Kubernetes-native recovery (pod restarts, readiness/liveness probes reused unchanged from the existing Compose healthchecks) — no new recovery mechanism invented.

**Documentation required:** `docs/deployment/kubernetes.md`, explicitly and prominently subordinate to the primary Compose documentation; `deploy/compose/multi-node.md`.

**OSS/contributor impact:** genuinely positive — an organization already running Kubernetes now has a real, tested path to contribute to or deploy GaiaOS without first learning Docker Compose.

**Free/self-hosted verification path:** k3s (free, self-hostable, the standard lightweight-Kubernetes choice for exactly this use case) in CI and for any real deployer — never a paid managed Kubernetes service, though one may of course be used voluntarily by a deployer who already has one.

**Acceptance criteria:** the k3s smoke test passes in CI on its scheduled cadence.

**Explicit non-goals:** no HPA, no multi-cluster federation, no claim that this is a "production-ready" path (it is a tested, documented, optional capability) — restated explicitly here because this is the single most likely place for well-intentioned scope creep to occur.

---

## Milestone 3 — Supply-Chain & Container Security Hardening

**Purpose:** Close the dependency-vulnerability-scanning, SBOM, image-digest-pinning, and GitHub Actions SHA-pinning gaps that have been correctly deprioritized as "nice to have" across every prior phase, and are now appropriate to close given the stronger bar "approaching v1.0" implies.

**Problem being solved:** no automated mechanism currently tells the project when a dependency (Python or container base image) has a known vulnerability; container images and GitHub Actions are pinned by mutable tag, not immutable digest/SHA.

**Why it belongs in Phase 8:** this is exactly "harden," the third step of the brief's own preferred "complete → harden → verify → release" sequence — not new capability, closing known, named, long-standing gaps.

**Existing architecture reused:** the existing `dependency-audit.yml`/Dependabot infrastructure (Phase 4 M1, confirmed actively merging real PRs as of the Phase 4/5 audits) — this milestone extends it, doesn't replace it.

**Proposed architecture:** (1) `pip-audit` added as a CI step (free, open-source, no paid vulnerability-database dependency); (2) a generated SBOM (CycloneDX format, via a free, open-source generator) published as a release artifact; (3) all four Dockerfiles' base images pinned by digest (`@sha256:...`) instead of tag; (4) all GitHub Actions pinned by commit SHA instead of version tag, with Dependabot configured to keep SHA pins current (Dependabot supports this natively, no new tooling required).

**Components affected:** `Dockerfile`, `Dockerfile.worker`, `Dockerfile.admin_ui`, every `.github/workflows/*.yml` file, `.github/dependabot.yml`.

**Dependencies:** none — fully independent, can run in parallel with every other Phase 8 milestone.

**Implementation order:** (1) `pip-audit` CI step; (2) SBOM generation; (3) image-digest pinning (verified via a full CI rebuild to confirm nothing breaks); (4) Actions SHA-pinning.

**Security implications:** this milestone's entire point — directly closes real, named supply-chain gaps.

**DevOps implications:** digest-pinned images require a deliberate, explicit update process going forward (a digest doesn't auto-update the way a tag like `3.12-slim` conceptually implies) — Dependabot's native support for both container-digest and Actions-SHA updates means this doesn't become a new manual burden, but it should be documented so a future contributor understands why the Dockerfile has a long hash instead of a friendly tag.

**Testing strategy:** a full CI run against digest-pinned images and SHA-pinned actions, proving the pin doesn't break any existing build/test/deploy step; `pip-audit` run against the current dependency set as a baseline (any pre-existing findings triaged, not silently ignored, before this milestone is considered done).

**Failure/recovery strategy:** N/A — build-time/CI concern, not a runtime failure mode.

**Documentation required:** `docs/phase8/supply_chain_security.md` — why digest/SHA pinning, how Dependabot keeps them current, how to read the published SBOM.

**OSS/contributor impact:** positive — a published SBOM and active vulnerability scanning are exactly what a security-conscious potential adopter or contributor checks for before trusting a project.

**Free/self-hosted verification path:** `pip-audit` and CycloneDX generation are both free, open-source, and run entirely in CI with no paid service.

**Acceptance criteria:** `pip-audit` runs clean (or with every finding explicitly triaged/accepted in writing) against current dependencies; all four Dockerfiles use digest pins; all GitHub Actions use SHA pins; a real SBOM is generated and published for the v0.8.0 release candidate.

**Explicit non-goals:** no commercial SCA/vulnerability platform (Snyk, etc.) — `pip-audit` and Dependabot, both free, are sufficient and consistent with the free-first mandate.

---

## Milestone 4 — API Stability Contract & v1.0 Versioning Policy

**Purpose:** Formalize, in writing, exactly what "v1.0" promises about API stability — which endpoints are covered, what counts as a breaking change, and the deprecation process for anything that needs to change after the promise is made.

**Problem being solved:** `/api/v1` has been additive-only by informal convention since Phase 4 M10; real external consumers (SDK, CLI, research-API users) now exist and deserve a written, binding commitment, not an informal habit.

**Why it belongs in Phase 8:** per ADR-803, this is the actual definition of "v1.0" this roadmap uses — it is not optional polish, it is the finish line's own definition.

**Existing architecture reused:** the `/api/v1` vs. `/api/v2` prefix policy (already established, Phase 4 M10); `docs/api/CHANGELOG.md` (already established, Phase 3 M10/Phase 4 M10) as the durable record this policy already assumed would exist.

**Proposed architecture:** a new `docs/api/STABILITY.md` — the formal contract: every currently-stable endpoint listed explicitly, the deprecation timeline (e.g., a minimum notice period before removal), what does and doesn't count as breaking (adding an optional field: not breaking; removing or renaming a field: breaking; changing a status code's meaning: breaking), and the process for proposing an exception.

**Components affected:** documentation only — no code change (this milestone doesn't change the API, it formalizes the promise about it).

**Dependencies:** none — independent of every other Phase 8 milestone.

**Implementation order:** (1) audit every current `/api/v1/*` endpoint against the OpenAPI spec to produce the definitive "what's covered" list (mechanical, using the already-generated spec — no manual re-derivation); (2) write the stability policy itself; (3) cross-link from the SDK's own documentation (Phase 7 M4) so SDK consumers see the same promise their generated client is built against.

**Security implications:** none directly, though a stable, well-documented API contract is itself a factor in how confidently external integrators build on the platform, which has second-order security-hygiene value (a clear contract reduces the chance of a consumer relying on undocumented, unstable behavior in a way that becomes a real problem later).

**DevOps implications:** the OpenAPI-drift-check (Phase 4 M10) should be extended to also fail if a *breaking* change (per this milestone's own definition) is detected on a stability-covered endpoint without a corresponding `/v2` path — the concrete, structural enforcement mechanism that makes this policy more than a document nobody checks against.

**Testing strategy:** a new CI check implementing the breaking-change detection described above, tested against a deliberately-introduced breaking change to a fixture endpoint, asserting it's correctly caught.

**Failure/recovery strategy:** N/A — a documentation and CI-policy milestone.

**Documentation required:** `docs/api/STABILITY.md` (the primary deliverable), a link from `README.md` and the SDK's own README.

**OSS/contributor impact:** significant and positive — a documented stability contract is one of the clearest signals of project maturity to both contributors (who now know what "breaking" means when reviewing a PR) and external adopters.

**Free/self-hosted verification path:** the breaking-change-detection CI check runs entirely locally/in CI, no external dependency.

**Acceptance criteria:** `docs/api/STABILITY.md` published; the breaking-change CI check correctly catches a deliberately-introduced fixture violation.

**Explicit non-goals:** this milestone does not freeze the API from ever changing — it defines the *process* for change, which is a meaningfully different and more useful commitment than "nothing will ever change."

---

## Milestone 5 — Automated Release Publishing

**Purpose:** Replace the manual tag-and-hope release process with CI-driven, automatic publishing — GitHub Releases generated from tags automatically, with real release notes, so the publication gap the Phase 7 audit found (real tags, zero published Releases, a public branch far behind local history) becomes structurally impossible to recur.

**Problem being solved:** named directly and specifically in the Phase 7 audit as its most consequential finding — a real, working release history existed only in local `git log`, invisible to anyone visiting the public repository.

**Why it belongs in Phase 8:** this is release engineering, the literal last word in the brief's own preferred sequence ("complete → harden → verify → release") — the appropriate phase to finally build the mechanism, not just fix the one-time gap again.

**Existing architecture reused:** the existing tag-based versioning scheme (`docs/releases/Versioning.md`), the existing OpenAPI/requirements-range drift-check CI idiom (Phase 4/5/7 precedent) — this milestone applies that same "make it structurally impossible to go stale" discipline to the release-publishing step itself, the fourth or fifth application of a pattern this project has now proven it trusts.

**Proposed architecture:** a GitHub Actions workflow triggered on tag push (`v*`) that (1) generates release notes automatically from the commits since the last tag (grouped by conventional-commit type — `feat`, `fix`, `docs`, etc., all already in consistent use per this project's commit history across every phase reviewed in this engagement), (2) publishes a real GitHub Release pointing at the tag, (3) attaches the SBOM (Milestone 3) as a release artifact, (4) runs `docs/releases/Versioning.md`'s drift-check (Phase 7) as a release-blocking gate, not just an informational CI check — a tag cannot be released if the versioning doc doesn't already describe it.

**Components affected:** new `.github/workflows/release.yml`.

**Dependencies:** conceptually benefits from Milestone 4's stability policy existing (so release notes can correctly flag breaking vs. non-breaking changes) and Milestone 3's SBOM (attached as an artifact) — sequenced after both for this reason, though not a hard blocking dependency in the sense that it couldn't technically be built first.

**Implementation order:** (1) release-notes generation from conventional commits; (2) GitHub Release publishing automation; (3) SBOM attachment; (4) the versioning-doc-drift release gate.

**Security implications:** the release workflow needs a scoped `GITHUB_TOKEN` permission (`contents: write` for this specific workflow only, not repo-wide) — least-privilege, consistent with the `permissions:` block discipline already established in `ci.yml` since Phase 1.

**DevOps implications:** this is the single change most likely to prevent the exact Critical finding (§1) that closed out the Phase 7 audit from ever recurring — the highest DevOps-value item in this entire roadmap.

**Testing strategy:** a dry-run against a test tag on a fork/test branch, verifying correct release-notes generation and the versioning-doc gate correctly blocking a deliberately-stale-doc scenario.

**Failure/recovery strategy:** a failed release workflow must fail loudly and block the release, never partially publish (e.g., a Release created but the SBOM attachment failing silently) — an explicit, tested all-or-nothing requirement.

**Documentation required:** `docs/phase8/release_automation.md` — the workflow's exact behavior, so a future maintainer understands what happens automatically versus what still requires a human decision (choosing the version number itself, per the brief's own "do not invent intermediate versions" principle, remains a deliberate human act — this milestone automates *publishing*, not *deciding to release*).

**OSS/contributor impact:** high — real, discoverable release notes and a real Releases page are exactly what makes a project's history legible to a newcomer deciding whether to adopt or contribute.

**Free/self-hosted verification path:** entirely GitHub Actions-native, no paid service, no external dependency beyond GitHub itself (which the project already depends on for hosting).

**Acceptance criteria:** the dry-run test (above) passes; the versioning-doc-drift gate demonstrably blocks a deliberately-stale scenario.

**Explicit non-goals:** this milestone does not change the versioning scheme itself, and does not automate the *decision* of when to cut a release or what version number to use — those remain deliberate human judgment calls, consistent with the brief's own explicit instruction not to invent versions during planning or automation.

---

## Milestone 6 (Capstone) — v1.0 Release Readiness Review

**Purpose:** The final "verify" step before "release" — a complete, evidence-based confirmation that every condition this roadmap and its six predecessor audits have named as necessary for a genuine v1.0 is actually true, gathered into one document, immediately before the v1.0.0 tag is cut (the actual cutting of which remains outside this planning document's scope, per the brief's explicit rules).

**Problem being solved:** without a single, final, cumulative checklist, "are we actually done" risks being answered by momentum (everything else finished, so we must be) rather than by evidence — exactly the failure mode this entire seven-audit engagement has existed to prevent at every smaller scale, now applied one last time at the largest scale.

**Why it belongs in Phase 8:** it is the literal capstone of "complete → harden → verify → release" — everything before it is complete/harden, this milestone is verify, and its output is the direct input to the (out-of-scope-for-this-document) release action itself.

**Existing architecture reused:** every audit checklist produced across this engagement (Phase 4 E.2/E.3, Phase 5 E.3/E.4, Phase 6 §4/§6, Phase 7 §14) — this milestone's job is to re-run them one final time, cumulatively, not invent a new checklist from scratch.

**Proposed architecture:** a single `docs/releases/V1_READINESS.md` document, structured as a literal checklist against every open item named across all seven prior audits plus Milestones 1–5 of this phase, each item marked with concrete, checkable evidence (a link to a passing CI run, a specific test name, a specific commit) — not a narrative summary, a verifiable ledger.

**Components affected:** documentation only, though producing it requires re-verifying (not just re-reading) every item, exactly as every prior audit in this engagement has insisted on doing rather than trusting a prior "done" label.

**Dependencies:** all of Milestones 1–5 (this is genuinely the capstone — it verifies their outputs, it cannot precede them).

**Implementation order:** (1) compile the cumulative checklist from all seven prior audits' open/closed items; (2) independently re-verify each "closed" item is still actually true at the current commit, not assumed from history (the exact discipline this engagement's audits have modeled throughout); (3) confirm Milestones 1–5's own acceptance criteria are met; (4) produce the final `V1_READINESS.md` with a clear, evidence-backed go/no-go recommendation.

**Security implications:** re-verifies every security-relevant closed finding across all seven prior audits one final time before a stability promise (Milestone 4) makes future changes harder to make freely.

**DevOps implications:** none new — this is a verification exercise over already-built infrastructure.

**Testing strategy:** N/A in the traditional sense — the "test" is the re-verification process itself, applied with the same rigor this engagement's own audits have used (direct file/commit evidence, not trusting a prior label).

**Failure/recovery strategy:** if the review finds a genuinely open item, the honest, correct outcome is delaying v1.0.0 until it's closed — explicitly stated as an acceptable outcome of this milestone, not a failure of the roadmap.

**Documentation required:** `docs/releases/V1_READINESS.md` (the entire deliverable).

**OSS/contributor impact:** a public, evidence-backed readiness document is itself a strong trust signal — "here is exactly why we believe this is ready," not just a version-number assertion.

**Free/self-hosted verification path:** the entire review is a documentation/verification exercise against the existing, already-free CI and testing infrastructure — no new dependency of any kind.

**Acceptance criteria:** `V1_READINESS.md` is complete, every item has concrete evidence (not a narrative claim), and the document's own conclusion is an explicit go/no-go — a go recommendation is the trigger for the (out-of-scope) actual v1.0.0 release action; a no-go recommendation, if the evidence genuinely supports it, is an equally legitimate and equally required output of this milestone.

**Explicit non-goals:** this milestone does not cut the v1.0.0 tag or publish the release itself — per the brief's explicit rule against creating tags/releases during planning, that action happens after this document exists and recommends it, as a separate, deliberate human act.

---

## What Was Deliberately Rejected for Phase 8

- **A third manual multi-node evidence-review milestone** — replaced by ADR-801's event-driven alternative, a strictly better use of the same underlying concern.
- **Production Kubernetes support (HPA, multi-cluster, managed-K8s assumptions)** — per ADR-802, no evidence justifies it; the narrow dev-only path is the entire justified scope.
- **A dedicated Prometheus/TimescaleDB migration** — the Phase 7 audit already found this unjustified at current scale (Milestone 1 of this phase uses the *existing* persisted-telemetry table, not a new time-series database).
- **Any new domain agent, reasoning capability, or research feature** — nothing in Phase 8's mission (governance and finish-line hardening) calls for one; the Agent Plugin Architecture remains the correct path for anyone, including a future contributor, who has a genuine new-domain need.
- **A Phase 9** — per the Finish-Line Assessment, no evidence-based case exists for one; see `finish_line_assessment.md` for the full reasoning.
