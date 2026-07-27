# Phase 4 – Milestone 9: Admin Observability Dashboard Architecture

## 1. Executive Summary

Milestone 9 introduces `admin_ui/` — a lightweight, standalone React 18 + TypeScript + Vite web application providing real-time operator observability for GaiaOS.

The dashboard integrates:
- **Phase 3 M9**: Observability metrics (p50/p95 latency, success rate, cost estimate).
- **Phase 4 M3**: Alert incidents history (firing vs. resolved status).
- **Phase 4 M6**: Automated database backup & restore drill audit logs.
- **Phase 4 M7**: Worker scaling advisory signals (`queue_depth`, `worker_utilization_pct`, `recommended_pool_size`).

---

## 2. Architectural Design & Boundary Enforcement

### 2.1 Independent Deployment Unit
`admin_ui` is built as an autonomous static SPA served by Nginx (`Dockerfile.admin_ui`).
- **No Shared Code**: Does not import Python backend code or share dependency trees.
- **No Private API Access**: Consumes only public, versioned HTTP endpoints under `/api/v1/admin/*` and `/api/v1/auth/login`.
- **Role Enforcement**: Inherits strict RBAC — requires `Role.ADMIN` JWT issued by `/api/v1/auth/login`.

### 2.2 Network & Reverse Proxy Architecture

```
                                [ Operator Browser ]
                                         │
                                         ▼ (Port 3000)
                              ┌──────────────────────┐
                              │ admin_ui Container   │
                              │ (Nginx static + proxy)│
                              └──────────┬───────────┘
                                         │ (internal docker net)
                                         ▼ http://app:8000/api/
                              ┌──────────────────────┐
                              │   GaiaOS App (FastAPI)│
                              └──────────────────────┘
```

1. **Development (`npm run dev`)**: Vite dev server listens on `http://localhost:3000` and proxies `/api` requests to `http://localhost:8000`.
2. **Production (`docker-compose`)**: Nginx listens on port 80 (mapped to host `3000`), serves static assets, and proxies `/api/` traffic to `http://app:8000/api/` inside the Docker network.

---

## 3. Polling vs. Streaming Design

Per Milestone 9 specification, live updates use configurable HTTP polling (default: 30 seconds):
- **Hook**: `usePoller(fetcher, intervalMs)` manages automated background execution.
- **Configurability**: Controlled via `VITE_POLL_INTERVAL_MS` without code changes.
- **Graceful Degredation**: If API requests fail due to network outage or container restart, pages display an `ApiUnreachable` banner while continuing background retries.

---

## 4. CI Workflow

A dedicated, isolated GitHub Action workflow (`.github/workflows/admin_ui_ci.yml`) validates the frontend:
- **Node 20**: Uses native Node.js 20 environment with npm caching.
- **Linting**: ESLint strict configuration (`npm run lint`).
- **Type Checking**: TypeScript compiler check (`npm run typecheck`).
- **Testing**: Vitest component suite (`npm run test`).

---

## 5. Security & RBAC Considerations

- **Authentication**: JWT tokens stored in `localStorage` and sent via `Authorization: Bearer <token>`.
- **Zero New Surface**: Uses existing `RequireRole(Role.ADMIN)` FastAPI dependencies. Non-admin requests receive HTTP 403 Forbidden.
- **XSS & Headers**: Nginx sets proper cache control (`no-cache` for HTML, immutable for hashed assets).
