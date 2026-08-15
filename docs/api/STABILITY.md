# GaiaOS Public API — v1.0 Stability Contract & Versioning Policy

## 1. Overview & Policy Statement

GaiaOS provides formal semantic stability guarantees for all public HTTP API endpoints operating under the `/api/v1/` prefix.

This contract defines the binding commitment made to external integrators, SDK clients (`gaiaos-sdk`), CLI consumers (`gaiaos`), and automated research pipelines.

- **Stable Prefix**: All operations under `/api/v1/` are subject to the stability guarantees defined in this document.
- **Root Landing Route (`GET /`)**: The root landing route (`/`) is inventoried for discoverability but is **excluded** from the `/api/v1/` stability contract.
- **Internal Routes**: Routes starting with `/internal/` (e.g. `/internal/smoke-job`) are internal infrastructure utilities and are excluded from the public OpenAPI specification and stability contract.

---

## 2. Stability Guarantees (`/api/v1/`)

### Backward-Compatible (Non-Breaking) Changes
The following additive changes may be introduced in minor or patch updates to `/api/v1/` without bumping the API major version:
1. **New Endpoints**: Adding a new endpoint under `/api/v1/`.
2. **New HTTP Methods**: Adding a new HTTP method to an existing `/api/v1/` path.
3. **Optional Request Parameters**: Adding new optional query parameters, header parameters, or optional fields in request bodies.
4. **New Response Fields**: Adding new fields to response JSON objects or expanding response enums.
5. **Deprecation Annotations**: Adding `deprecated: true` to an endpoint or schema property (see Section 4 for deprecation timeline requirements).

### Breaking Changes (Forbidden In-Place on `/api/v1/`)
The following changes are classified as **breaking changes** and will **NEVER** be made in-place on a `/api/v1/` endpoint:
1. **Endpoint / Method Removal**: Deleting a `/api/v1/` endpoint or removing a supported HTTP method.
2. **Request Parameter Changes**: Removing a request parameter, changing its location or data type, or making an optional parameter required.
3. **Request Body Changes**: Removing a request body media type, removing schema properties, changing property types, or making optional properties required.
4. **Response Contract Changes**: Removing a HTTP status code (e.g., `200 OK` or `201 Created`), removing a response media type (e.g., `application/json`), removing response properties, changing property types, or making previously non-null properties nullable.
5. **Behavioral Contract Changes**: Altering the semantics of existing parameters or status codes.

---

## 3. Major Version Migration (`/v2/` Policy)

Per **ADR-803**, any breaking change to a `/api/v1/` operation requires a major version upgrade to a `/api/v2/` prefix.

- **Operation-Level Exemption**: A breaking change to a specific `/api/v1/path` operation (e.g., `POST /api/v1/investigations`) is permitted **only if an equivalent operation exists under `/api/v2/path`** (e.g., `POST /api/v2/investigations`) containing the updated contract. Unrelated `/v2/` endpoints do not exempt `/api/v1/` operations from stability enforcement.
- **Parallel Coexistence**: Deprecated `/api/v1/` endpoints will remain operational alongside `/api/v2/` endpoints throughout the documented deprecation notice period.

---

## 4. Deprecation Process & Notice Period

1. **Annotation**: Deprecated operations or schema fields are marked with `deprecated: true` in the OpenAPI specification.
2. **Documentation & Headers**: Deprecation details, migration guidelines, and planned sunset dates are documented in [`docs/api/CHANGELOG.md`](CHANGELOG.md). Responses include standard `Deprecation: @<timestamp>` and `Link: <...>; rel="deprecation"` HTTP headers.
3. **Minimum Notice Period**: Deprecated `/api/v1/` endpoints will be supported for a minimum notice period of **180 days** after deprecation before removal, and removal occurs only when an equivalent `/v2/` endpoint is active.

---

## 5. Covered `/api/v1/*` Endpoint Inventory (26 Endpoints)

The following 26 endpoints constitute the stable `/api/v1/` public API surface:

### Infrastructure & Health (3 endpoints)
- `GET /api/v1/ping`
- `GET /api/v1/health/live`
- `GET /api/v1/health/ready`

### Auth & Account Management (9 endpoints / methods)
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `GET /api/v1/auth/verify-email`
- `POST /api/v1/auth/resend-verification`
- `POST /api/v1/auth/request-reset`
- `POST /api/v1/auth/reset`
- `GET /api/v1/api-keys`
- `POST /api/v1/api-keys`
- `DELETE /api/v1/api-keys/{key_id}`

### Core Investigations & Agent Runtime (4 endpoints)
- `POST /api/v1/investigations`
- `GET /api/v1/investigations/{investigation_id}`
- `GET /api/v1/investigations/{investigation_id}/stream`
- `GET /api/v1/investigations/{investigation_id}/trace`

### Research & Analytics (3 endpoints)
- `GET /api/v1/research/hazard-events`
- `GET /api/v1/research/investigations`
- `GET /api/v1/research/patterns`

### Admin & Operations (7 endpoints / methods)
- `GET /api/v1/admin/metrics`
- `GET /api/v1/admin/metrics/prometheus`
- `GET /api/v1/admin/backups`
- `GET /api/v1/admin/restore-drills`
- `GET /api/v1/admin/alerts`
- `GET /api/v1/admin/alert-rules`
- `POST /api/v1/admin/alert-rules`
- `DELETE /api/v1/admin/alert-rules/{rule_id}`
