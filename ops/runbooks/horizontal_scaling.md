# Operational Runbook: Horizontal Scalability (Workers & Read Path)

## 1. Overview

GaiaOS supports horizontal scaling across two primary axes:
1. **Asynchronous Worker Pool Scaling**: Scaling the number of RQ background worker processes handling graph investigation jobs.
2. **Read-Replica Query Routing**: Routing heavy read-only analytical and metrics queries away from the primary PostgreSQL instance to read replicas.

---

## 2. Worker Pool Scaling

### 2.1 Scaling via Docker Compose
GaiaOS uses RQ background worker processes configured in `docker-compose.yml`. Scale workers dynamically using Docker Compose replica flags:

```bash
# Scale worker pool to 4 concurrent worker processes
docker compose up -d --scale worker=4
```

### 2.2 Telemetry & Scaling Metrics
The administration metrics API monitors queue depth and worker utilization to provide advisory pool size recommendations:

```http
GET /api/v1/admin/metrics?window=7d&group_by=complexity_tier
```

**Key Response Fields**:
- `queue_depth`: Total pending jobs in the worker queue.
- `worker_utilization_pct`: Percentage of worker capacity currently active.
- `recommended_pool_size`: Advisory worker pool size calculated via `workers.scaling_policy.recommended_pool_size()`.

---

## 3. Read-Replica Configuration

### 3.1 Environment Configuration
To enable PostgreSQL read-replica query routing, set the `READ_REPLICA_DATABASE_URL` environment variable:

```env
READ_REPLICA_DATABASE_URL=postgresql://replica_user:replica_pass@pg-replica.internal:5432/gaiaos
```

If `READ_REPLICA_DATABASE_URL` is omitted or `None`, GaiaOS routes all read requests directly to the primary database engine.

### 3.2 Dependency Injection & Fallback Semantics
FastAPI routes and internal analytical procedures consume `DbReadSessionDep` (backed by `db.session.get_read_session()`).

**Fallback Behavior**:
- During initial session acquisition and connection checkout, if the read-replica instance raises an `OperationalError` (connection refused, network partition), GaiaOS logs a warning (`db.read_replica_failed_falling_back_to_primary`) and acquires a primary DB session transparently.

---

## 4. Concurrent Load Testing

Run the multi-worker load test suite to verify worker concurrency, RQ job-locking, and Redis checkpoint key isolation:

```bash
python -m pytest -v tests/load/test_concurrent_worker_processing.py
```

The load test executes $N=4$ concurrent worker processes processing a burst of $M=100$ real investigation jobs calling `run_investigation_job()`, verifying 100% completion, zero double-processing, and complete checkpoint namespace isolation under `checkpoint:<investigation_id>:*`.

---

## 5. Observability & Future Work

- **Replica Replication Lag**: Future observability enhancements will query PostgreSQL's `pg_stat_replication` view to export `replication_lag_bytes` and `replication_lag_seconds` into Prometheus and admin metrics.

---

## 6. Phase 7 Milestone 5 Evaluation & Production Guidance

**Evaluation Verdict:** **Outcome B — Evidence Does Not Justify Multi-Node Scaling (Dated 2026-08-10)**.

For full evaluation details, see [`docs/phase7/scaling_evaluation_m5.md`](../../docs/phase7/scaling_evaluation_m5.md).

### Operational Directives:
1. **Primary Deployment Topology**: Single-node Docker Compose multi-process worker scaling (`docker compose up -d --scale worker=N`) remains the primary, fully-supported production deployment standard.
2. **Multi-Node Trigger Criteria**: Physical multi-node deployment across separate host boundaries remains deferred until empirical telemetry demonstrates one or more of the following:
   - `queue_depth > 10 \times WORKER_POOL_SIZE` ($>20$ jobs) sustained for $>15$ minutes.
   - `worker_utilization_pct = 100%` sustained for $>10$ minutes.
   - P95 queue wait time $>60$ seconds.

