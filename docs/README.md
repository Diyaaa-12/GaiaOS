# GaiaOS Documentation Hub

The central navigation index for all GaiaOS system architecture, contributor guides, API specifications, operational runbooks, phase roadmaps, and engineering audits.

---

## Getting Started
- **[Environment Setup](contributing/ENVIRONMENT_SETUP.md)** — Virtual environment setup, OS-specific notes (Windows/Linux/macOS), troubleshooting, and setup FAQ.
- **[First Pull Request Walkthrough](contributing/FIRST_PR.md)** — Step-by-step guide for first-time contributors from issue selection to PR submission.
- **[Project Structure Guide](contributing/PROJECT_STRUCTURE.md)** — Repository directory layout map and code placement decision matrix.
- **[Development & CI Workflow](contributing/DEVELOPMENT_WORKFLOW.md)** — Local quality checks (`python scripts/verify.py`), static analysis, and CI parity.

## Architecture
- **[System Architecture Specification](Architecture.md)** — Primary specification detailing the four architectural layers.
- **[Phase 2 Deep Dives](phase2/agent_contract.md)** — Architectural specs for reasoning agents, adaptive planner, causal chains, eval harness, and RAG strategy.
- **[Phase 3 Deep Dives](phase3/authentication.md)** — Specs for authentication, rate limiting, hazard ingestion, task queues, and replan loops.
- **[Phase 4 Deep Dives](phase4/admin_dashboard.md)** — Specs for admin UI dashboard, alerting, citation integrity, geocoding, and worker scaling.
- **[Phase 5 Deep Dives](phase5/slos.md)** — Specs for SLO burn-rate alerting and [Async Resource Lifecycle](phase5/async_resource_lifecycle.md).
- **[Phase 6 Deep Dives](phase6/simulation_calibration.md)** — Specs for resilience layer (caching, retry, circuit breaker), real-data ingestion pipelines (Copernicus, ERA5, GDELT, ArXiv), OSM boundaries, and MinIO object storage.
- **[Phase 7 Deep Dives](phase7/)** — Specs for reasoning trace explainability, pattern mining, Python SDK, CLI wizard, scaling evaluation, OpenMetrics enrichment, and deployment governance.
- **[Plugin Development Guide](PLUGIN_DEVELOPMENT.md)** — Reference for building and registering third-party domain agent plugins.

## API Documentation
- **[OpenAPI Specification](api/openapi/openapi.json)** — Machine-readable OpenAPI 3.1.0 JSON specification.
- **[v1.0 API Stability Contract](api/STABILITY.md)** — Semver commitments for all `/api/v1/` endpoints; backward-compatibility policy and `/api/v2/` upgrade criteria.
- **[Public Research API](research-api/README.md)** — Specification for public research endpoints and dataset export archives (ADR-504).
- **[API Changelog](api/CHANGELOG.md)** — Historical changelog of API endpoints and version contracts.

## Contributor Guides
- **[Step-by-Step How-To Guides](contributing/HOW_TO_GUIDES.md)** — Procedural guides for adding domain agents, API endpoints, DB models, and writing tests.
- **[Domain Agent Contribution Guide](CONTRIBUTING_AGENTS.md)** — Detailed specification for building and testing new environmental risk agents.
- **[General Contributing Guidelines](../CONTRIBUTING.md)** — Code of conduct, branching conventions, and pull request requirements.

## Operations & Runbooks
- **[Deployment & Operations Runbook](../ops/runbooks/deployment_and_operations.md)** — Production deployment sequence, migration hooks, MinIO notes, Prometheus setup, Grafana dashboard import, and DB maintenance.
- **[Disaster Recovery Runbook](../ops/runbooks/disaster_recovery.md)** — Backup restoration and disaster recovery procedures.
- **[Incident Response Runbook](../ops/runbooks/incident_response.md)** — Severity levels, escalation pathways, and incident handling SOP.
- **[Migration Rollback Runbook](../ops/runbooks/migration_rollback.md)** — Standard operating procedures for rolling back database migrations.
- **[Kubernetes Deployment Guide](deployment/kubernetes.md)** — Optional multi-node Helm chart setup, k3s smoke testing, and non-production Kubernetes path (ADR-802).

## Releases
- **[Versioning Strategy](releases/Versioning.md)** — Milestone tagging rules, release cadence, and semantic versioning strategy. Includes v1.0.0 finish-line designation.
- **[v1.0 Release Readiness](releases/V1_READINESS.md)** — Pre-GA readiness checklist covering CI, security, API stability, and documentation gates.
- **[Automated Release Publishing Guide](phase8/release_automation.md)** — CI-driven release workflow, conventional commits, CycloneDX v1.6 SBOM generation, and release readiness gate.
- **[Phase 1 Roadmap](Roadmap_Phase1.md)** — Foundation, FastAPI, PostgreSQL (PostGIS + pgvector), Gateway.
- **[Phase 2 Roadmap](Roadmap_Phase2.md)** — Multi-Agent Reasoning Core, LangGraph, Literature RAG.
- **[Phase 3 Roadmap](Roadmap_Phase3.md)** — Auth, Rate Limiting, RQ Workers, SSE Stream, Eval Suite.
- **[Phase 4 Roadmap](Roadmap_Phase4.md)** — CI Integrity, Admin Dashboard, Alerting, Citation Mapping, Geocoding, Worker Scaling.
- **[Phase 5 Roadmap](Roadmap_Phase5.md)** — Evaluation, Plugins, Read Replica Scaling, SLOs, Public Research API.
- **[Phase 6 Roadmap](Roadmap_Phase6.md)** — Resilience Layer, Real-Data Ingestion (Copernicus, ERA5, GDELT, ArXiv), Simulation Calibration, MinIO.
- **[Phase 7 Roadmap](Roadmap_Phase7.md)** — Explainability, Pattern Mining, Python SDK, CLI Wizard, Scaling Evaluation, OpenMetrics, Deployment Governance.
- **[Phase 8 Roadmap](Roadmap_Phase8.md)** — Release Automation, API Stability Contract, Supply-Chain Security, Scaling Alerting, Kubernetes, v1.0 GA.

## Phase 8 — v1.0.0 GA Engineering Documents
- **[Release Automation](phase8/release_automation.md)** — Conventional commit changelog, SBOM generation, and CI release gate architecture.
- **[Supply-Chain & Container Security](phase8/supply_chain_security.md)** — Dependabot corrective workflows, Trivy scanning, and SBOM attestation.
- **[Automated Scaling Alerting](phase8/scaling_alerting.md)** — Scaling-trigger alert integration with the existing threshold pipeline.

## Audits
- **[Engineering Audit Index](../Audit_Index.md)** — Master index tracking all engineering audit reports and status matrix through v1.0.0.
- **[Phase 1 Final Audit](audits/GaiaOS_Phase1_Final_Audit.md)** | **[Phase 1 Production Audit](audits/GaiaOS_Phase1_Production_Audit.md)**
- **[Phase 2 Final Audit](audits/GaiaOS_Phase2_Final_Audit.md)**
- **[Phase 3 Final Audit](audits/GaiaOS_Phase3_Final_Audit.md)**
- **[Phase 4 Final Audit](audits/GaiaOS_Phase4_Final_Audit.md)**
- **[Phase 5 Final Audit](audits/GaiaOS_Phase5_Final_Audit.md)**
- **[Phase 6 Final Audit](audits/GaiaOS_Phase6_Final_Audit.md)**
- **[Phase 7 Final Audit](audits/GaiaOS_Phase7_Final_Audit.md)**
- **[Post-v1 Architectural Assessment](audits/post_v1_assessment.md)** — Repository-evidenced review of all Phase 9 gap candidates; verdict: v1.0.0 is the engineering finish line.
- **[Finish-Line Assessment](audits/finish_line_assessment.md)** — Defines "done" for GaiaOS, maintenance-mode watch conditions, and explicit non-goals going forward.

## Governance & Community
- **[Support Guidelines](../SUPPORT.md)** — Community support channels, issue triage taxonomy, and maintainer SLA.
- **[Security Policy](../SECURITY.md)** — Vulnerability disclosure policy and private reporting guidelines.
- **[Code of Conduct](../CODE_OF_CONDUCT.md)** — Contributor Covenant Code of Conduct.
- **[Apache 2.0 License](../LICENSE)** — Open-source software license.
