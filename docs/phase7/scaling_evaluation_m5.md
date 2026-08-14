# Horizontal Scaling Maturity Evaluation — Phase 7 Milestone 5

**Date:** 2026-08-10  
**Evaluator:** GaiaOS Core Engineering  
**Outcome:** **Outcome B — Evidence Does Not Justify Multi-Node Scaling (Deferral)**

> [!NOTE]
> **Automated Monitoring (Phase 8 M1)**: As of Phase 8 Milestone 1, manual historical scaling evaluations documented here are supplemented by continuous, automated alerting via the alerting engine (`AlertRule`, `AlertIncident`, `alert_evaluation_job.py`). See [`docs/phase8/scaling_alerting.md`](../phase8/scaling_alerting.md) for live trigger definitions and incident lifecycle details.

---

## 1. Overview & Evaluation Context

Phase 5 Milestone 7 implemented the advisory worker pool sizing policy (`workers.scaling_policy.recommended_pool_size()`) and exposed runtime queue telemetry via `workers.scaling_policy.get_scaling_metrics()` and `GET /api/v1/admin/metrics`. Phase 5 M7 also established single-node worker load benchmarks (`tests/load/test_concurrent_worker_processing.py`).

Per the evidence-first principles of GaiaOS (Architecture v1.0 through Phase 6) and the explicit requirements of Phase 7 Milestone 5, this document performs an empirical evaluation of available repository telemetry, test benchmarks, and scaling policy criteria to determine whether expanding GaiaOS worker deployment to physically separate, network-partitioned multi-node topologies is justified.

---

## 2. Quantitative Telemetry & Trigger Condition Audit

### 2.1 Trigger Criteria Definition
`docs/phase4/worker_scaling.md` §5 documents three specific quantitative thresholds for triggering horizontal worker infrastructure scaling:

1. **SLA Queue Depth Threshold**: `queue_depth > 10 \times \text{WORKER\_POOL\_SIZE}` sustained for $>3$ consecutive evaluation cycles (15 minutes). With default `WORKER_POOL_SIZE = 2` (`config/settings.py`), this represents a sustained queue depth $>20$ jobs.
2. **Sustained Worker Utilization**: `worker_utilization_pct = 100\%` sustained for $>2$ consecutive evaluation cycles (10 minutes).
3. **Queue Wait Latency**: P95 queue wait time exceeds `WORKER_TARGET_MAX_WAIT_S` (60.0 seconds).

### 2.2 Empirical Audit & Telemetry Scope
- **Current-State Queue Inspection**: In steady-state operation when idle, `workers.scaling_policy.get_scaling_metrics()` queries Redis `len(Queue("default"))` and returns `current_queue_depth = 0`.
- **Persisted Telemetry Sampling Architecture**: GaiaOS records periodic scaling telemetry samples in a dedicated PostgreSQL table (`scaling_telemetry_samples`) via `workers.jobs.scaling_telemetry_job.run_scaling_telemetry_job()`. Queue depth, worker utilization %, active worker count, busy worker count, and advisory pool size are sampled and stored with a 30-day automated retention pruning policy (`workers.scaling_policy.prune_scaling_telemetry_samples()`). Historical time-series windows (`1d`, `7d`, `30d`, `90d`) are evaluated dynamically via `workers.scaling_policy.get_historical_scaling_telemetry()`.
- **Audit Verdict**: **No available repository telemetry or test evidence demonstrates that these trigger conditions have been met.**

---

## 3. Single-Node Capacity & Load Benchmark Analysis

### 3.1 Single-Host Multi-Process Worker Scaling
GaiaOS background jobs execute under Redis Queue (RQ) using Docker Compose worker process scaling:
```bash
docker compose up -d --scale worker=N
```
Single-node vertical and process scaling allows expanding the worker pool up to host CPU and memory limits (e.g. 4 to 16 worker processes per host) without introducing cross-node networking overhead or remote database session management complexity.

### 3.2 Load Test Benchmark Verification
Phase 5 M7 established the single-node concurrent worker load test suite (`tests/load/test_concurrent_worker_processing.py`):
- **Workload Scale**: $N=4$ concurrent worker processes processing a burst of $M=100$ real investigation jobs calling `run_investigation_job()`.
- **Completion Benchmark**: All 100 jobs finished with 100% completion in `FinishedJobRegistry` and zero failed jobs.
- **Process Join Timeout**: Enforced by a 120-second process join timeout in the test suite (`p.join(timeout=120)`). *Note: This 120-second timeout is a test acceptance threshold for process execution, not a measured P95 or P99 job execution latency.*
- **Checkpoint Isolation**: 100% namespace isolation verified across all 100 investigation IDs under Redis key pattern `gaiaos:checkpoint:<investigation_id>:*`.
- **Resource Lifecycle**: Async database engines (`dispose_engine()`), Redis connections, and HTTP clients are disposed and re-initialized per job inside `_async_run_investigation()`, preventing event-loop cross-contamination across process re-use.

---

## 4. Multi-Node Architectural Analysis (Contingency Review)

While multi-node scaling is deferred under Outcome B, an architectural review of what physical multi-node distribution would require highlights the speculative technical debt avoided at this stage:

1. **Remote Redis Connection & Network Partitions**: Moving workers to physically separate VPS instances requires exposing Redis over encrypted TLS/VPC networks, configuring TCP keepalives and socket timeouts, and handling network partition retries during RQ job lock renewal.
2. **PostgreSQL Connection Pooling**: Physically separate nodes increase concurrent connection overhead on the primary database, necessitating PgBouncer connection pooling and explicit read-replica fallback handling across WAN boundaries.
3. **Operational Overhead**: Multi-node topologies require cross-node log aggregation, node health monitoring, and distributed secret management — complexity that is unjustified while single-node process scaling (`docker compose up -d --scale worker=N`) handles current workloads cleanly.

---

## 5. Downstream Milestone Scope Impact Analysis

As explicitly governed by `Roadmap_Phase7.md`:

- **Milestone 6 (Distributed Metrics Aggregation)**:
  - `Roadmap_Phase7.md` §176-200 specifies that Milestone 6's scope is conditional on Milestone 5.
  - **Verdict under Outcome B**: Single-node in-memory/Redis/Postgres metrics (Phase 4 M9 / Phase 5 M8) remain complete and sufficient. Multi-node Prometheus scraping across separate worker hosts is out of scope for Phase 7.
- **Milestone 7 (Kubernetes / Helm Deployment Path)**:
  - `Roadmap_Phase7.md` §203-228 explicitly recommends that if Milestone 5 does not justify multi-node scaling, Milestone 7 is deferred in its entirety.
  - **Verdict under Outcome B**: Milestone 7 is formally deferred to Phase 8.

---

## 6. Verification Summary & Next Steps

1. **Operational Standard**: Single-node Docker Compose multi-process worker scaling (`docker compose up -d --scale worker=N`) remains the verified, primary production deployment path.
2. **Re-Evaluation Triggers**: Multi-node scaling will be re-evaluated if production telemetry collected in future phases demonstrates sustained queue depths $>20$ for $>15$ minutes or P95 queue wait times $>60$ seconds.
3. **Roadmap Alignment**: Milestone 5 is complete under **Outcome B**. Phase 7 continues with Milestone 1–4 track priorities.
