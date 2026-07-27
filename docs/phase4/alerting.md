# GaiaOS Phase 4 — Milestone 3: Production Monitoring & Alerting

## 1. Overview
Milestone 3 implements an automated production monitoring and alerting engine for GaiaOS. Threshold-based rules evaluate metric rollups on a scheduled worker job, persisting incidents in PostgreSQL and notifying external systems via a channel-agnostic webhook interface.

---

## 2. Architecture & Design

### 2.1 Decoupled Evaluation Worker
Rule evaluation runs inside a recurring background RQ worker job (`workers/jobs/alert_evaluation_job.py`) registered with RQ Scheduler (`workers/scheduler.py`). Rule evaluation has **zero impact** on API request latency.

---

### 2.2 Default System Rules & Idempotent Seeding
On initial system deployment or fresh database startup, the evaluation job checks if the `alert_rules` table is empty and idempotently seeds default system rules:

| Rule Name | Metric | Threshold | Window | Severity | Consecutive Cycles |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `high_p95_latency` | `investigation.p95_latency_ms` | > 10000.0 ms | `15m` | `warning` | 1 |
| `high_job_failure_rate` | `investigation.job_failure_rate` | > 0.10 (10%) | `1h` | `critical` | 1 |

---

### 2.3 Flapping Suppression Policy
To prevent alert fatigue from noisy metrics fluctuating around a threshold boundary, rules enforce a `consecutive_cycles` policy. A notification triggers only when a metric violates the threshold for $N$ consecutive evaluation runs.

---

### 2.4 Incident Lifecycle & Persistence
Incidents are stored in PostgreSQL (`alert_incidents` table) to maintain queryable history for administrative visibility:
- **Firing:** When a threshold violation occurs, an incident is created with `status="firing"`, `fired_at=now()`, and a firing notification is dispatched via webhook.
- **Ongoing Firing:** Consecutive evaluations update `last_value` and increment `consecutive_violations`.
- **Resolution:** When metrics return below threshold, the incident transitions to `status="resolved"` with `resolved_at=now()`, and a resolution notification is dispatched.

---

### 2.5 Webhook Notification Channel & Resiliency
`WebhookNotificationChannel` implements the `NotificationChannel` Protocol using `httpx.AsyncClient`:
- Formats structured JSON payloads compatible with Slack, Discord, and PagerDuty webhooks.
- Implements exponential backoff retries (3 retries by default).
- Non-blocking delivery: delivery failures update `notification_failures` telemetry counter without crashing the worker job.

---

## 3. Public Admin API Endpoints

All admin endpoints require `Role.ADMIN` (`RequireRole(Role.ADMIN)`):

- `GET /api/v1/admin/alerts` — List current and historical incidents (supports `?status=firing|resolved`).
- `GET /api/v1/admin/alert-rules` — List all configured alert rules.
- `POST /api/v1/admin/alert-rules` — Idempotent upsert (create or update) an alert rule by `name`.
- `DELETE /api/v1/admin/alert-rules/{rule_id}` — Remove an alert rule.
