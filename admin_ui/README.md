# GaiaOS Admin UI

Frontend observability dashboard for GaiaOS operators — built with React 18, TypeScript, and Vite.

## Overview

`admin_ui` is a standalone, single-page application (SPA) serving as the operator UI for GaiaOS.
It surfaces:
- **Metrics**: Aggregated p50/p95 latency, success rate, and cost rollups (`GET /api/v1/admin/metrics`).
- **Alerts**: Real-time alert incident history with firing and resolved status badges (`GET /api/v1/admin/alerts`).
- **Workers**: Advisory worker scaling metrics and pool-size recommendations (`GET /api/v1/admin/metrics`).
- **Backups**: Historical database backup audit log (`GET /api/v1/admin/backups`).

## Architecture & Production Deployment

- **Decoupled Architecture**: Completely separate deployable. Does not share code or build pipeline with the Python backend.
- **Authentication**: Uses standard GaiaOS JWT (`Role.ADMIN` required). Token stored in `localStorage`.
- **API Proxy**:
  - **Local Development**: Vite dev server proxies `/api` calls to `http://localhost:8000`.
  - **Production Docker Compose**: Nginx container proxies `/api/` calls to `http://app:8000/api/` inside the container network.
- **Graceful Failure**: If the backend is unreachable, pages render a non-blocking `ApiUnreachable` banner while continuing background polling.

## Local Development Setup

### Prerequisites
- Node.js 20+
- npm 10+

### Installation & Execution
```bash
# Navigate to directory
cd admin_ui

# Install dependencies
npm install

# Start development server (http://localhost:3000)
npm run dev

# Run ESLint
npm run lint

# Run TypeScript type check
npm run typecheck

# Run component tests (Vitest)
npm run test
```

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `VITE_API_BASE_URL` | `""` (relative) | Base URL for backend API requests. In dev/docker, relative `/api` is proxied. |
| `VITE_POLL_INTERVAL_MS` | `30000` | Polling refresh interval in milliseconds (30–60s recommended). |
