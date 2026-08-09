# Single-Node Deployment & Infrastructure Governance — Phase 7 Milestone 7

**Status:** Completed (Completed as a deployment-governance/evaluation milestone under M5 Outcome B; the original Kubernetes/Helm implementation remains deferred to Phase 8)  
**Target:** GaiaOS Production Infrastructure & Operations  
**Date:** 2026-08-10  

---

## 1. Executive Summary & Governance Verdict

Phase 7 Milestone 7 establishes the production deployment governance standards for GaiaOS.

Per the conditional dependency rules established in `Roadmap_Phase7.md` §184–191 and §241, Milestone 7's scope is explicitly governed by Milestone 5's empirical scaling evaluation. Because Milestone 5 resulted in **Outcome B (Evidence-Backed Scaling Deferral)**, physically separate multi-node worker deployments and Kubernetes/Helm container orchestration are **formally deferred to Phase 8 in their entirety**.

Single-node multi-process Docker Compose container scaling (`docker compose up -d --scale worker=N`) remains the primary, fully-verified production deployment architecture.

---

## 2. Production Deployment Architecture (Single-Node Docker Compose)

### 2.1 Services Topology
GaiaOS deploys as a multi-container stack defined in `docker-compose.yml`:
- **`app`**: FastAPI REST API gateway serving public research endpoints, admin observability APIs, and OpenMetrics scraping targets (`GET /api/v1/admin/metrics/prometheus`).
- **`worker`**: Redis Queue (RQ) background job worker processes handling graph investigations, data ingestion pipelines (`usgs`, `noaa`, `copernicus`, `era5`, `gdelt`, `arxiv`), longitudinal pattern mining, and automated database backups.
- **`postgres`**: Primary PostgreSQL database instance equipped with `PostGIS` and `pgvector` extensions for geospatial and vector similarity search.
- **`redis`**: Caching, rate-limiting, job queue management, and per-source circuit breaker state machine (`resilience/circuit_breaker.py`).

### 2.2 Dynamic Worker Process Scaling
Horizontal worker pool scaling is executed via Docker Compose process replication on the single host:
```bash
# Scale background worker pool to N concurrent processes
docker compose up -d --scale worker=4
```
Each scaled worker runs as an independent container/process and consumes jobs from the shared Redis queue with 100% namespace isolation under `gaiaos:checkpoint:<investigation_id>:*`.

### 2.3 Container Resource Limits & Health Checks
All services in `docker-compose.yml` enforce operational resource limits and automated health checks:
- **`postgres`**: Configured with `healthcheck` (`pg_isready -U gaiaos`), memory limits (`deploy.resources.limits.memory: 1g`), and CPU reservations.
- **`redis`**: Configured with `healthcheck` (`redis-cli ping`), memory limits (`memory: 512m`), and appendonly persistence.
- **`app`**: Configured with readiness health probes (`GET /api/v1/health/ready`) validating database connections, PostGIS extension presence, pgvector extension presence, and Redis ping.

---

## 3. Read-Replica Architecture & Failover

### 3.1 Environment Configuration
Heavy analytical queries (metrics aggregation, pattern mining, complex investigation reads) support PostgreSQL read-replica session routing via environment configuration:
```env
READ_REPLICA_DATABASE_URL=postgresql://replica_user:replica_pass@pg-replica.internal:5432/gaiaos
```

### 3.2 Dynamic Fallback Semantics
Read sessions are acquired via `DbReadSessionDep` (`db.session.get_read_session()`).
- If `READ_REPLICA_DATABASE_URL` is omitted, requests route directly to the primary database.
- If the replica instance raises an `OperationalError` during checkout (e.g. network partition, node reboot), GaiaOS logs `db.read_replica_failed_falling_back_to_primary` and automatically falls back to acquiring a primary database session, helping maintain request availability by falling back to the primary database session.


---

## 4. Operational Runbooks Reference

Operational procedures, backup policies, and disaster recovery workflows are maintained in dedicated runbooks under `ops/runbooks/`:

1. **[`ops/runbooks/deployment_and_operations.md`](../../ops/runbooks/deployment_and_operations.md)**: Deployment steps, environment variable configuration, container startup sequences, and health monitoring.
2. **[`ops/runbooks/horizontal_scaling.md`](../../ops/runbooks/horizontal_scaling.md)**: Worker scaling commands (`--scale worker=N`), advisory metric monitoring (`GET /api/v1/admin/metrics`), read-replica configuration, and M5 Outcome B production guidance.
3. **[`ops/runbooks/disaster_recovery.md`](../../ops/runbooks/disaster_recovery.md)**: Local PostgreSQL dumps, Redis RDB/AOF snapshot verifications, automated backup retention cleanup (`workers/jobs/backup_job.py`), and point-in-time recovery steps.
4. **[`ops/runbooks/incident_response.md`](../../ops/runbooks/incident_response.md)**: Alert response procedures, circuit breaker states, and service degradation protocols.

---

## 5. Phase 8 Scope Boundary & Multi-Node Trigger Criteria

### 5.1 Explicitly Deferred Scope (Phase 8)
The following infrastructure components are **strictly out of scope for Phase 7** and must NOT be introduced:
- Kubernetes manifests (`k8s/`), Helm charts (`charts/`), or K3s/Minikube deployment configurations.
- Multi-host worker process distribution across separate physical VPS/cloud nodes.
- Kubernetes Horizontal Pod Autoscaler (HPA) or cluster autoscaling configurations.
- Terraform or cloud provider infrastructure-as-code modules for managed Kubernetes clusters (GKE, EKS, AKS).
- External Pushgateway containers or remote multi-host Prometheus scraping layers.

### 5.2 Empirical Re-Evaluation Triggers
Physical multi-node scaling and Kubernetes deployment will be re-evaluated in Phase 8 **only if** production telemetry collected in steady-state operation meets one or more of the following quantitative triggers established in Phase 7 Milestone 5:
1. **SLA Queue Depth Threshold**: `queue_depth > 10 \times WORKER_POOL_SIZE` ($>20$ jobs) sustained for $>15$ minutes ($>3$ evaluation cycles).
2. **Sustained Worker Utilization**: `worker_utilization_pct = 100%` sustained for $>10$ minutes ($>2$ evaluation cycles).
3. **Queue Wait Latency**: P95 queue wait time exceeds 60 seconds (`WORKER_TARGET_MAX_WAIT_S`).
