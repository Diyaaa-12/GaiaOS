# GaiaOS Phase 4 — CI & Deployment Verification Design Document

## 1. Overview
Prior to Phase 4, GaiaOS CI workflows verified that the primary `app` container built and passed liveness checks, but left `worker` (`Dockerfile.worker`) and `scheduler` container images unverified end-to-end. Milestone 1 closes this operational risk by establishing complete deployment integrity verification and supply-chain hardening.

---

## 2. Architecture & Design

### 2.1 Background Worker Deployment Verification
CI now provisions the full service stack (`app`, `worker`, `scheduler`, `postgres`, `redis`) via `docker compose up -d --build --wait app worker scheduler`.

Deployment integrity is validated end-to-end via an internal smoke-job workflow:
1. **Endpoint:** `POST /internal/smoke-job` (mounted on the root application).
2. **Environment Safety Gate:** The endpoint checks `Settings.GAIAOS_ENV`. If equal to `"prod"`, the endpoint immediately raises HTTP 404 Not Found, preventing accidental exposure in production deployments.
3. **Pipeline Reuse:** In non-prod environments, calling `POST /internal/smoke-job` reuses the standard production `InvestigationRepository` to record a test investigation and enqueues `run_investigation_job` into the RQ `default` queue.
4. **Execution & Telemetry:** An active RQ worker picks up the job, executes the investigation graph, updates the status in PostgreSQL to `complete`, and emits standard telemetry (`JobStarted` / `JobCompleted`).
5. **Verification Script:** `tests/test_worker_image_smoke.py` polls PostgreSQL / API until job completion (30s timeout). If the job fails or times out, container logs (`worker`, `scheduler`) are dumped to stdout and CI fails loudly.

---

## 3. Supply-Chain Hardening

### 3.1 Lockfiles & Reproducible Container Builds
- **`requirements/base.lock`**: Pinned version snapshot of all production runtime dependencies.
- **`requirements/dev.lock`**: Pinned version snapshot of development, testing, and linting dependencies.
- `Dockerfile` and `Dockerfile.worker` install dependencies directly from `base.lock`, guaranteeing byte-for-byte reproducible container environments across builds.

### 3.2 Automated Vulnerability Audits & Dependabot
- **`.github/dependabot.yml`**: Configures weekly automated version update checks for `pip` packages and GitHub Actions.
- **`.github/workflows/dependency-audit.yml`**: Scheduled weekly workflow (and on PRs touching requirements) running `pip-audit -r requirements/base.lock -r requirements/dev.lock` to catch known CVEs proactively.
