# GaiaOS Public API — Versioning & Changelog

## Public API Versioning Policy

GaiaOS enforces strict semantic versioning guarantees on all public HTTP API endpoints under the `/api/` prefix.

### Stability Guarantees (`/api/v1/`)
- All endpoints under `/api/v1/` form the current **stable public API contract**.
- Backward-compatible additions (new endpoints, optional request parameters, new non-null response fields) may be introduced in minor/patch updates to `/api/v1/`.
- **Breaking changes** (removing endpoints, renaming parameters, altering response schemas, or removing response fields) will **NEVER** be made in-place on `/api/v1/`.
- Any breaking change requires a new major API version prefix (e.g. `/api/v2/`). Deprecated `/api/v1/` endpoints will remain supported throughout a documented migration window.

---

## Change Log

### [1.0.0] — Phase 3 Milestone 10

#### Added
- **API Key Authentication (`X-API-Key`)**:
  - External consumers can authenticate via `X-API-Key: gaios_live_...` headers.
  - `POST /api/v1/api-keys`: Issue new API keys. Restricted to `RESEARCHER` and `ADMIN` roles. Returns the raw secret key **only once**.
  - `GET /api/v1/api-keys`: List active API keys owned by user or all keys for `ADMIN`.
  - `DELETE /api/v1/api-keys/{key_id}`: Revoke an API key. Restricted to key owner or `ADMIN`.
- **API Key Rate Limiting**:
  - Dedicated rate limit scope (`scope="api_key"`) for API-key-authenticated requests.
- **Audit Logging**:
  - Access log includes non-sensitive `key_id` identifier for per-key audit logging without credential leakage.

### Phase 4 Milestone 10 — Documentation & API Specification Publishing

#### Added
- **OpenAPI 3.1.0 Specification Publishing**:
  - Automated spec generation script (`scripts/generate_openapi_spec.py`).
  - Machine-readable specification saved to [`docs/api/openapi/openapi.json`](openapi/openapi.json).
- **OpenAPI Schema Hardening**:
  - Internal infrastructure routes (such as `/internal/smoke-job`) are excluded from published API schema using FastAPI's native `include_in_schema=False`.
- **CI Specification Drift Enforcement**:
  - CI workflow checks generated spec against committed version (`git diff --exit-code`) to prevent schema drift.

