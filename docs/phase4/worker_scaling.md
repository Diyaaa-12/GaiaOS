# Worker Scaling Policy & Resource Configuration

## 1. Overview & Architectural Principles

GaiaOS Phase 4 Milestone 7 introduces an explicit, deterministic **Worker Scaling Policy** and **Container Resource Limits**.

### Core Guarantees
- **Advisory Only**: Worker scaling recommendations are purely advisory and diagnostic. The system computes recommended worker pool sizes and exposes them via admin metrics APIs and structured logs.
- **NO Autoscaling**: GaiaOS does **NOT** perform automatic horizontal process or container scaling. No Kubernetes HPA, Kafka brokers, or automated process spawning are active.
- **Manual Operator Control**: Scaling actions (e.g. increasing `WORKER_POOL_SIZE` or container replica count) remain strictly manual operator decisions.

---

## 2. Resource Configuration & Limits

All core services in `docker-compose.yml` (`app`, `worker`, `scheduler`) are governed by configurable CPU and memory resource limits:

| Service | Environment Variable (CPU) | Environment Variable (Memory) | Default CPU | Default Memory |
| :--- | :--- | :--- | :--- | :--- |
| **API (`app`)** | `APP_CPU_LIMIT` | `APP_MEMORY_LIMIT` | `1.0` | `512M` |
| **Worker (`worker`)** | `WORKER_CPU_LIMIT` | `WORKER_MEMORY_LIMIT` | `1.0` | `512M` |
| **Scheduler (`scheduler`)** | `SCHEDULER_CPU_LIMIT` | `SCHEDULER_MEMORY_LIMIT` | `0.5` | `256M` |

> [!NOTE]
> Resource limits are configured using the standard Docker Compose Specification (`deploy.resources.limits`). Modern Docker Compose v2+ engines (`docker compose up`) enforce `deploy.resources.limits` natively on single-node daemon setups as well as Swarm/orchestrated deployments. Older v1 legacy `docker-compose` CLI tools parse `deploy` keys for validation without active cgroup enforcement.

---

## 3. Scaling Recommendation Formula

The advisory pool size is computed by `recommended_pool_size()` in `workers/scaling_policy.py`:

$$\text{Capacity Required} = \frac{\text{Queue Depth} \times \text{Avg Job Duration (s)}}{\text{Target Max Wait (s)}}$$

$$\text{Recommended Pool Size} = \max\left(\text{WORKER\_POOL\_SIZE}, \lceil \text{Capacity Required} \rceil\right)$$

### Formula Characteristics
1. **Minimum Bound**: Never recommends a pool size smaller than the configured `WORKER_POOL_SIZE` (default: `2`).
2. **Safe Input Clamping**: Negative or invalid queue depths and non-positive SLA wait targets are clamped safely to prevent mathematical panics or negative capacity output.
3. **Zero Side Effects**: The calculation is a pure, deterministic function with zero infrastructure side effects.

---

## 4. Observability & Admin API Integration

### Structured Logging
The RQ scheduler periodically emits an advisory scaling summary log:
```json
{
  "event": "scaling.summary",
  "current_pool_size": 2,
  "queue_depth": 14,
  "worker_utilization_pct": 100.0,
  "recommended_pool_size": 7
}
```

### Admin Observability API
The `GET /api/v1/admin/metrics` endpoint incorporates real-time scaling fields:
```json
{
  "window": "7d",
  "group_by": "complexity_tier",
  "rollups": [...],
  "queue_depth": 14,
  "worker_utilization_pct": 100.0,
  "recommended_pool_size": 7
}
```

---

## 5. Future Autoscaling Trigger Conditions

While autoscaling is deferred, future production deployments (Phase 5+) may consider automated scaling triggers under the following documented criteria:
1. **SLA Threshold Violation**: `queue_depth` remains $> 10 \times \text{WORKER\_POOL\_SIZE}$ for more than 3 consecutive evaluation cycles (15 minutes).
2. **Sustained High Utilization**: `worker_utilization_pct` stays at `100%` for $> 10$ minutes.
3. **Queue Wait Latency**: P95 queue wait time exceeds `WORKER_TARGET_MAX_WAIT_S` (60 seconds).
