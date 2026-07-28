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

## API Documentation
- **[OpenAPI Specification](api/openapi/openapi.json)** — Machine-readable OpenAPI 3.1.0 JSON specification.
- **[API Changelog](api/CHANGELOG.md)** — Historical changelog of API endpoints and version contracts.

## Contributor Guides
- **[Step-by-Step How-To Guides](contributing/HOW_TO_GUIDES.md)** — Procedural guides for adding domain agents, API endpoints, DB models, and writing tests.
- **[Domain Agent Contribution Guide](CONTRIBUTING_AGENTS.md)** — Detailed specification for building and testing new environmental risk agents.
- **[General Contributing Guidelines](../CONTRIBUTING.md)** — Code of conduct, branching conventions, and pull request requirements.

## Operations & Runbooks
- **[Disaster Recovery Runbook](../ops/runbooks/disaster_recovery.md)** — Backup restoration and disaster recovery procedures.
- **[Incident Response Runbook](../ops/runbooks/incident_response.md)** — Severity levels, escalation pathways, and incident handling SOP.
- **[Migration Rollback Runbook](../ops/runbooks/migration_rollback.md)** — Standard operating procedures for rolling back database migrations.

## Releases
- **[Versioning Strategy](releases/Versioning.md)** — Milestone tagging rules, release cadence, and semantic versioning strategy.
- **[Phase 1 Roadmap](Roadmap_Phase1.md)** — Foundation, FastAPI, PostgreSQL (PostGIS + pgvector), Gateway.
- **[Phase 2 Roadmap](Roadmap_Phase2.md)** — Multi-Agent Reasoning Core, LangGraph, Literature RAG.
- **[Phase 3 Roadmap](Roadmap_Phase3.md)** — Auth, Rate Limiting, RQ Workers, SSE Stream, Eval Suite.
- **[Phase 4 Roadmap](Roadmap_Phase4.md)** — CI Integrity, Admin Dashboard, Alerting, Citation Mapping, Geocoding, Worker Scaling.

## Audits
- **[Engineering Audit Index](../Audit_Index.md)** — Master index tracking all engineering audit reports and status matrix.
- **[Phase 1 Final Audit](audits/GaiaOS_Phase1_Final_Audit.md)** | **[Phase 1 Production Audit](audits/GaiaOS_Phase1_Production_Audit.md)**
- **[Phase 2 Final Audit](audits/GaiaOS_Phase2_Final_Audit.md)**
- **[Phase 3 Final Audit](audits/GaiaOS_Phase3_Final_Audit.md)**
- **[Phase 4 Final Audit](audits/GaiaOS_Phase4_Final_Audit.md)**

## Governance & Community
- **[Support Guidelines](../SUPPORT.md)** — Community support channels, issue triage taxonomy, and maintainer SLA.
- **[Security Policy](../SECURITY.md)** — Vulnerability disclosure policy and private reporting guidelines.
- **[Code of Conduct](../CODE_OF_CONDUCT.md)** — Contributor Covenant Code of Conduct.
- **[Apache 2.0 License](../LICENSE)** — Open-source software license.
