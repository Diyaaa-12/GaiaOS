# GaiaOS Versioning Strategy

This document details the versioning strategy, tag evolution, and milestone release roadmap for GaiaOS.

## Release Map

| Git Tag / Version | Scope | Status |
|---|---|---|
| Pre-tag | Phase 1 | Complete |
| v0.2.0  | Phase 2 | Complete |
| v0.3.0  | Phase 3 | Complete |
| v0.4.0  | Phase 4 Complete | Complete |
| v0.4.1  | Repository Governance | Complete |
| v0.4.2  | Community Health | Complete |
| v0.4.3  | Contributor Experience | Complete |
| v0.4.4  | Open Source Release Polish | Complete (Final Readiness) |
| v0.5.0  | Phase 5 Milestones 1–2 (Evaluation & Repository Integrity) | Complete |
| v0.5.1  | Phase 5 Milestones 3–5 (Uncertainty, Multi-Agent Collaboration & Cross-Domain Synthesis) | Complete |
| v0.5.2  | Phase 5 Milestone 6 (Agent Plugin Architecture) | Complete |
| v0.5.3  | Phase 5 Milestones 7–8 (Read Replica Scaling & SLO Burn-Rate Alerting) | Complete |
| v0.5.4  | Phase 5 Capstone (Public Research API & Dataset Publishing) | Complete |
| v0.6.0  | Phase 6 Milestone 1 (Resilience Layer: Caching, Retry & Circuit Breaker) | Complete |
| v0.6.1  | Phase 6 Milestones 2–3 (Copernicus, ERA5, GDELT Ingestion & OSM Administrative Boundaries) | Complete |
| v0.6.2  | Phase 6 Milestones 4–5 (ArXiv Open-Access Corpus & Offline Simulation Calibration) | Complete |
| v0.6.3  | Phase 6 Milestone 6 (MinIO Self-Hosted Object Storage Option) | Complete |
| v0.6.4  | Phase 6 Operational Readiness & Polish | Complete |
| v0.7.0  | Phase 7 Milestones 1–3 (Explainability, Pattern Mining & Python SDK) | Complete |
| v0.7.1  | Phase 7 Milestone 4 (CLI Wizard & Developer Tooling) | Complete |
| v0.7.2  | Phase 7 Milestones 5–6 (Scaling Evaluation & Distributed Metrics Aggregation) | Complete |
| v0.7.3  | Phase 7 Milestone 7 (Deployment Governance & Scale Governance) | Complete |
| v0.7.4  | Phase 7 Final Engineering Audit Exit (Persisted Telemetry & Governance Hardening) | Complete |
| v1.0.0  | Phase 8 Capstone & GaiaOS v1.0 General Availability | Complete |

---

## Historical Releases

- **v0.2.0** — Phase 2: Multi-Agent Reasoning Core, LangGraph Integration & Literature RAG
- **v0.3.0** — Phase 3: Durable Execution, JWT/API Key Auth & Evaluation Suite

---

## Release Strategy

GaiaOS follows Semantic Versioning (`v0.X.Y` / `v1.X.Y`):

- **MAJOR versions** (`v1.0.0`) represent production General Availability.
- **MINOR versions** (`v0.4.0`, `v0.5.0`, `v0.6.0`, `v0.7.0`) represent major phase completions.
- **PATCH versions** (`v0.4.1`, `v0.5.1`, `v0.6.1`, `v0.7.1`) represent milestone releases within a phase series.

### The v0.4.x Open Source Readiness Series

- **v0.4.0** — Phase 4 Complete
- **v0.4.1** — Repository Governance
- **v0.4.2** — Community Health
- **v0.4.3** — Contributor Experience
- **v0.4.4** — Open Source Release Polish

### The v0.5.x Planetary Intelligence Series

- **v0.5.0** — Phase 5 Milestones 1–2 (Evaluation & Repository Integrity)
- **v0.5.1** — Phase 5 Milestones 3–5 (Uncertainty, Multi-Agent Collaboration & Cross-Domain Synthesis)
- **v0.5.2** — Phase 5 Milestone 6 (Agent Plugin Architecture)
- **v0.5.3** — Phase 5 Milestones 7–8 (Read Replica Scaling & SLOs / Error Budgets)
- **v0.5.4** — Phase 5 Capstone (Public Research API & Dataset Publishing)

### The v0.6.x Real-Data Grounding & Resilience Series

- **v0.6.0** — Phase 6 Milestone 1 (Resilience Layer: Caching, Retry & Circuit Breaker)
- **v0.6.1** — Phase 6 Milestones 2–3 (Copernicus, ERA5, GDELT Ingestion & OSM Administrative Boundaries)
- **v0.6.2** — Phase 6 Milestones 4–5 (ArXiv Open-Access Corpus & Offline Simulation Calibration)
- **v0.6.3** — Phase 6 Milestone 6 (MinIO Self-Hosted Object Storage Option)
- **v0.6.4** — Phase 6 Operational Readiness & Polish

### The v0.7.x Explainability, Ecosystem & Governance Series

- **v0.7.0** — Phase 7 Milestones 1–3 (Explainability, Pattern Mining & Python SDK)
- **v0.7.1** — Phase 7 Milestone 4 (CLI Wizard & Developer Tooling)
- **v0.7.2** — Phase 7 Milestones 5–6 (Scaling Evaluation & Distributed Metrics Aggregation)
- **v0.7.3** — Phase 7 Milestone 7 (Deployment Governance & Scale Governance)
- **v0.7.4** — Phase 7 Final Engineering Audit Exit (Persisted Telemetry & Governance Hardening)

### The v1.0.x Production Release Series

- **v1.0.0** — Phase 8 Capstone & GaiaOS v1.0 General Availability Release

---

## Future Releases

- **v1.1.0** — Phase 9 (Advanced Planetary Agentic Autonomy & Enterprise Scale)


---

## Public API Versioning & Stability

All public endpoints under `/api/v1/` are subject to the binding [v1.0 API Stability Contract](../api/STABILITY.md). Backward-compatible additions may occur in patch releases; breaking changes require an operation-level `/api/v2/` upgrade.

---

## Automated Release Publishing

All release tags matching `v*` trigger automated GitHub Release publishing, conventional commit changelog generation, CycloneDX v1.6 SBOM artifact building, and versioning documentation validation. See the [Automated Release Publishing Guide](../phase8/release_automation.md) for full architecture and maintainer procedures.

*(Refer to the project roadmap for current scope.)*

