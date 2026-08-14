# Automated Scaling-Trigger Alerting — Phase 8 Milestone 1

## 1. Overview & Architectural Principles

Phase 8 Milestone 1 introduces continuous, automated alerting for the quantitative worker scaling triggers established in Phase 5 M7 and Phase 7 M5.

Per **ADR-801** (`docs/Roadmap_Phase8.md`), GaiaOS replaces periodic manual multi-node evidence audits with live, event-driven monitoring. When production workload telemetry breaches defined operational thresholds, the system automatically detects the breach, manages the incident lifecycle, and emits operator notifications.

### Core Guarantees
- **Pure Continuous Observability**: Automated alerting detects threshold breaches continuously without manual intervention.
- **Strictly Advisory Policy**: The worker pool policy remains advisory (`workers/scaling_policy.py`). No worker provisioning, container spawning, or Kubernetes autoscaling is executed.
- **Reused Operational Engine**: Plugs directly into the Phase 4 M3 / Phase 5 M8 alerting framework (`AlertRule`, `AlertIncident`, `alert_evaluation_job.py`, and `WebhookNotificationChannel`). Zero custom alert engines or TSDBs added.
- **Flapping Suppression**: Requires consecutive evaluation cycle violations (`consecutive_cycles`) before triggering notifications, preventing transient workload spikes from generating alert noise.

---

## 2. Quantitative Scaling Triggers & Rule Definitions

All three scaling trigger rules are seeded automatically in the `alert_rules` table during initial evaluation if empty:

| Rule Name | Metric | Comparison | Threshold | Window | Consecutive Cycles | Evaluation Cadence | Operational Rationale |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| `scaling_queue_depth_breach` | `scaling.queue_depth` | `gt` | `10 * WORKER_POOL_SIZE` *(dynamic)* | `15m` | `4` | 5 min | Queue depth sustained above SLA bound for 15 minutes (4 consecutive 5-min cycles: T=0, T=5, T=10, T=15). |
| `scaling_worker_utilization_breach` | `scaling.worker_utilization_pct` | `gte` | `100.0%` | `15m` | `4` | 5 min | All workers 100% busy sustained for >10 minutes (4 consecutive 5-min cycles: T=0, T=5, T=10, T=15). |
| `scaling_p95_queue_wait_breach` | `scaling.p95_queue_wait_s` | `gt` | `60.0s` (`WORKER_TARGET_MAX_WAIT_S`) | `15m` | `1` | 5 min | P95 queue wait duration exceeding SLA wait target across the sliding window. |

---

## 3. Data Collection & Calculation Semantics

### 3.1 SLA Queue Depth Threshold
- **Dynamic Rule Evaluation**: The threshold is evaluated dynamically at query time as `10 * get_settings().worker_pool_size` (default: 20 jobs for pool size 2). If `WORKER_POOL_SIZE` is reconfigured, the evaluation threshold adjusts automatically.
- **Telemetry Source**: Sampled periodically by `workers.jobs.scaling_telemetry_job` and stored in `scaling_telemetry_samples`.
- **Sustained Duration**: Requires `queue_depth > 10 * WORKER_POOL_SIZE` across 4 consecutive 5-minute evaluation cycles (15 minutes elapsed from T=0 to T=15m).

### 3.2 Sustained Worker Utilization
- **Utilisation Metric**: Calculated as `(busy_workers / active_workers) * 100.0` across RQ worker instances.
- **Sustained Duration**: Requires `worker_utilization_pct >= 100.0%` across 4 consecutive 5-minute evaluation cycles (15 minutes elapsed from T=0 to T=15m), guaranteeing the breach has persisted for >10 minutes.

### 3.3 Mathematical P95 Queue-Wait Metric
- **Canonical Per-Job Observation**: Queue wait time `(started_at - enqueued_at)` is recorded **exactly once per job execution** when an RQ worker picks up a job and emits a `JobStarted` metric event.
- **Database Persistence**: Persisted into PostgreSQL `metrics` table (`queue_wait_ms` column, `nullable=True`). Historical unobserved rows (`NULL`) are explicitly filtered out (`WHERE queue_wait_ms IS NOT NULL`).
- **Mathematical Percentile Calculation**: Evaluated via PostgreSQL `PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY queue_wait_ms)` converted to seconds.

---

## 4. Incident Lifecycle & Notification Behavior

1. **Cycle 1 (Breach Detected)**: An `AlertIncident` record is created in PostgreSQL with `status = "firing"` and `consecutive_violations = 1`. If `consecutive_cycles > 1`, notification is suppressed.
2. **Cycles 2 & 3 (Breach Continues)**: `consecutive_violations` increments to `2` and `3`. Notification remains suppressed while `consecutive_violations < consecutive_cycles`.
3. **Cycle 4 (Threshold Met)**: `consecutive_violations` reaches `consecutive_cycles` (`4`). Webhook notification is dispatched to `ALERT_WEBHOOK_URL`.
4. **Subsequent Breached Cycles**: While the condition remains continuously breached, `consecutive_violations` increments, but **zero duplicate notifications** are dispatched.
5. **Recovery Cycle**: When metrics return below threshold, the incident status transitions to `"resolved"`, and an `AlertResolution` webhook notification is emitted.

---

## 5. Verification & Testing Strategy

Automated tests cover all scaling rules and lifecycle transitions in `tests/test_scaling_alerting.py`:
- **Threshold & Evaluation Unit Tests**: Verify `gt` and `gte` comparisons, dynamic queue depth calculation, mathematical P95 queue wait computation, and null telemetry handling.
- **End-to-End Incident Lifecycle Integration Test**: Verifies firing creation, flapping suppression, single-notification dispatch on cycle requirement, duplicate notification suppression, and resolution.
