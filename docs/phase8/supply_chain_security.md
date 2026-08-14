# Supply-Chain & Container Security Hardening

This document outlines the security controls, container digest pinning standards, GitHub Actions commit SHA pinning rules, `pip-audit` vulnerability scanning policy, and CycloneDX Software Bill of Materials (SBOM) generation strategy in GaiaOS.

---

## 1. Container Base Image Digest Pinning

To guarantee reproducible, tamper-proof container builds and prevent upstream image mutation from breaking deployments, all container base images in GaiaOS are pinned to immutable SHA256 image digests (`image:tag@sha256:...`) alongside human-readable tag comments.

### Base Image Inventory

| Component / Path | Friendly Tag | Immutable SHA256 Digest | Pinned Syntax |
| --- | --- | --- | --- |
| App Server ([`Dockerfile`](file:///c:/Users/DIYA/OneDrive/Documents/Projects/GaiaOS/Dockerfile)) | `python:3.12-slim-bookworm` | `sha256:a116514e19457bcb7af7efe9c3dd0b9b71e85b317694e7882a1c52aa15a78134` | `FROM python:3.12-slim-bookworm@sha256:a116514e19457bcb7af7efe9c3dd0b9b71e85b317694e7882a1c52aa15a78134` |
| Background Worker ([`Dockerfile.worker`](file:///c:/Users/DIYA/OneDrive/Documents/Projects/GaiaOS/Dockerfile.worker)) | `python:3.12-slim-bookworm` | `sha256:a116514e19457bcb7af7efe9c3dd0b9b71e85b317694e7882a1c52aa15a78134` | `FROM python:3.12-slim-bookworm@sha256:a116514e19457bcb7af7efe9c3dd0b9b71e85b317694e7882a1c52aa15a78134` |
| Admin UI Builder ([`admin_ui/Dockerfile.admin_ui`](file:///c:/Users/DIYA/OneDrive/Documents/Projects/GaiaOS/admin_ui/Dockerfile.admin_ui)) | `node:20-alpine` | `sha256:fb4cd12c85ee03686f6af5362a0b0d56d50c58a04632e6c0fb8363f609372293` | `FROM node:20-alpine@sha256:fb4cd12c85ee03686f6af5362a0b0d56d50c58a04632e6c0fb8363f609372293 AS builder` |
| Admin UI Runtime ([`admin_ui/Dockerfile.admin_ui`](file:///c:/Users/DIYA/OneDrive/Documents/Projects/GaiaOS/admin_ui/Dockerfile.admin_ui)) | `nginx:1.27-alpine` | `sha256:65645c7bb6a0661892a8b03b89d0743208a18dd2f3f17a54ef4b76fb8e2f2a10` | `FROM nginx:1.27-alpine@sha256:65645c7bb6a0661892a8b03b89d0743208a18dd2f3f17a54ef4b76fb8e2f2a10 AS runtime` |
| PostGIS Database ([`infra/docker/postgres/Dockerfile`](file:///c:/Users/DIYA/OneDrive/Documents/Projects/GaiaOS/infra/docker/postgres/Dockerfile)) | `postgis/postgis:16-3.4` | `sha256:44126d872ac91993766c341e369c539e8196614321765d36a6f1bab0419a5fa5` | `FROM postgis/postgis:16-3.4@sha256:44126d872ac91993766c341e369c539e8196614321765d36a6f1bab0419a5fa5` |

---

## 2. GitHub Actions Commit SHA Pinning & Dependabot

To mitigate third-party GitHub Action supply-chain attack vectors (e.g. tag mutation or compromised action releases), all workflow steps in `.github/workflows/` pin third-party actions to full 40-character commit SHAs.

### Workflow Action Mappings

| Action Name | Release Tag | Immutable Commit SHA | Pinned Comment Syntax |
| --- | --- | --- | --- |
| `actions/checkout` | `v4.4.0` | `11d5960a326750d5838078e36cf38b85af677262` | `uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4.4.0` |
| `actions/setup-python` | `v5.6.0` | `a26af69be951a213d495a4c3e4e4022e16d87065` | `uses: actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065 # v5.6.0` |
| `actions/setup-node` | `v4.4.0` | `49933ea5288caeca8642d1e84afbd3f7d6820020` | `uses: actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020 # v4.4.0` |
| `azure/setup-helm` | `v4.3.1` | `1a275c3b69536ee54be43f2070a358922e12c8d4` | `uses: azure/setup-helm@1a275c3b69536ee54be43f2070a358922e12c8d4 # v4.3.1` |
| `actions/upload-artifact` | `v4.6.2` | `ea165f8d65b6e75b540449e92b4886f43607fa02` | `uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4.6.2` |

### Dependabot Automated Digest Updates

Dependabot is configured in [`.github/dependabot.yml`](file:///.github/dependabot.yml) to automatically monitor and submit pull requests for:
- Python packages (`pip` ecosystem in `/requirements`)
- GitHub Actions (`github-actions` ecosystem in `/`)
- Docker base images (`docker` ecosystem in `/`, `/admin_ui`, and `/infra/docker/postgres`)

---

## 3. `pip-audit` Vulnerability Scanning Policy

GaiaOS enforces dependency vulnerability scanning via `pip-audit` in [`.github/workflows/dependency-audit.yml`](file:///.github/workflows/dependency-audit.yml).

### Scanning Strategy & Lockfile Triage

- `pip-audit` checks Python dependencies against the Python Packaging Advisory Database (PyPA) and OSV.
- Lockfiles are audited sequentially:
  ```bash
  pip-audit -r requirements/base.lock
  pip-audit -r requirements/dev.lock
  ```
- **Triage Policy**: Any vulnerability detected with severity High/Critical blocks CI. If a vulnerability is reported in a transitive dependency without an immediate patch, an issue must be logged and explicit triage documented in `requirements/` with upstream fix tracking.

---

## 4. Software Bill of Materials (SBOM) Strategy

GaiaOS standardizes on **CycloneDX v1.6 JSON** format as its Software Bill of Materials specification.

### Single Canonical SBOM Generator

- **Tooling**: `cyclonedx-bom` (`cyclonedx-py` CLI harness)
- **Command**:
  ```bash
  cyclonedx-py requirements requirements/base.lock -o gaiaos-sbom.json
  ```
- **CI Artifact Publishing**: Integrated into [`.github/workflows/ci.yml`](file:///.github/workflows/ci.yml). Every successful CI run generates and uploads `gaiaos-sbom.json` as a workflow build artifact. The current artifact is the runtime Python dependency SBOM generated from `requirements/base.lock`; formal GitHub Release attachment is deferred until an actual release is created.
- **Release Strategy**: When formal release tags (e.g. Release Candidates) are published in the future, the generated `gaiaos-sbom.json` workflow artifact is attached directly to the GitHub Release.
