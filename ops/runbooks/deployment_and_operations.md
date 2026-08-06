# Deployment & Operations Runbook — GaiaOS

This operational guide details real-world deployment, database migrations, backup/restore procedures, Prometheus monitoring, PostgreSQL/Redis maintenance, and VPS troubleshooting.

---

## 1. Deployment Sequence

GaiaOS is designed for single-server VPS or multi-container containerized deployments using Docker Compose.

### Quick Start Deployment

1. **Clone Repository & Environment Setup**:
   ```bash
   git clone https://github.com/Diyaaa-12/GaiaOS.git
   cd GaiaOS
   cp .env.example .env
   ```
2. **Configure Secrets**:
   Set `POSTGRES_PASSWORD`, `JWT_SECRET_KEY`, and `MINIO_SECRET_KEY` (if using MinIO) in `.env`.
3. **Boot Stack**:
   ```bash
   docker compose up -d --build
   ```

### Execution Flow:
```
[Postgres & Redis Containers] (Healthcheck Passed)
       │
       ▼
[db_migrations Container] (Executes `alembic upgrade head` & exits 0)
       │
       ▼
[App, Worker & Scheduler Containers] (Boot after db_migrations success)
```

---

## 2. Migration Workflow

Migrations are managed via Alembic and executed automatically by the `db_migrations` container service during deployment.

- **Manual Migration Execution**:
  ```bash
  docker compose exec app alembic upgrade head
  ```
- **Downgrade / Rollback**:
  ```bash
  docker compose exec app alembic downgrade -1
  ```
- **Zero-Downtime Migration Rule**:
  Column removals or renames must be executed in two steps (add new column -> migrate application code -> drop old column) to preserve backwards compatibility across worker replicas.

---

## 3. Backup & Disaster Recovery Workflow

GaiaOS supports automated PostgreSQL database backups to local filesystem storage or self-hosted MinIO object storage.

### Backup Strategy
- Backups are triggered on a cron schedule (`BACKUP_CRON="0 2 * * *"`) by `workers.jobs.backup_jobs.run_postgres_backup_job`.
- Backups stream `pg_dump` directly to storage, compute SHA-256 checksums, and log `BackupCompleted` telemetry events.

### Automated Restore Drills
- Restore drills execute via `workers.jobs.backup_jobs.run_restore_drill_job` on `RESTORE_DRILL_CRON`.
- The drill downloads the latest backup, verifies SHA-256 checksum integrity against `BackupRecord.checksum`, restores to a temporary database, and verifies table row counts.

---

## 4. MinIO Self-Hosted Object Storage

To enable MinIO object storage:

1. Enable the `minio` Compose profile:
   ```bash
   COMPOSE_PROFILES=minio docker compose up -d
   ```
2. Update `.env`:
   ```env
   BACKUP_STORAGE_BACKEND=minio
   MINIO_ENDPOINT=http://minio:9000
   MINIO_ACCESS_KEY=minioadmin
   MINIO_SECRET_KEY=minioadmin_password
   MINIO_BUCKET=gaiaos-backups
   MINIO_AUTO_CREATE_BUCKET=true
   ```

---

## 5. Prometheus Monitoring & Observability

### Endpoints
- **Aggregated JSON Metrics**: `GET /api/v1/admin/metrics?window=7d&group_by=complexity_tier`
- **OpenMetrics Text Format**: `GET /api/v1/admin/metrics/prometheus`

### Authentication Strategy for Long-Lived Scrapers
Expiring user JWT bearer tokens are not suitable for automated Prometheus scraping. GaiaOS supports static metric scraper authentication via `PROMETHEUS_METRICS_TOKEN`:

1. Set `PROMETHEUS_METRICS_TOKEN` in `.env`:
   ```env
   PROMETHEUS_METRICS_TOKEN=my-long-lived-prometheus-scrape-token-12345
   ```
2. Configure `prometheus.yml`:
   ```yaml
   scrape_configs:
     - job_name: 'gaiaos'
       scrape_interval: 15s
       metrics_path: '/api/v1/admin/metrics/prometheus'
       bearer_token: 'my-long-lived-prometheus-scrape-token-12345'
       static_configs:
         - targets: ['localhost:8000']
   ```

### Grafana Dashboard Import
- **Dashboard File**: [`ops/dashboards/gaiaos-dashboard.json`](../dashboards/gaiaos-dashboard.json)
- **Import Procedure**:
  1. Open Grafana UI -> **Dashboards** -> **New** -> **Import**.
  2. Upload `ops/dashboards/gaiaos-dashboard.json` or paste its JSON content.
  3. Select your Prometheus data source when prompted (`DS_PROMETHEUS`).
- **Prerequisites**: Prometheus scraping `GET /api/v1/admin/metrics/prometheus` as configured above.

### OpenMetrics Implementation & Maintenance Note
GaiaOS uses lightweight, zero-dependency `MetricCounter` instances in `metrics/collector.py` instead of the third-party `prometheus_client` library. Any new counter added to `metrics/collector.py` must be explicitly formatted into `# HELP`, `# TYPE`, and sample lines in `get_prometheus_metrics()` in `app/api/v1/admin_metrics.py`.

---

## 6. Recommended Database & Cache Maintenance

### PostgreSQL Optimization & Autovacuum
- **Autovacuum Guidance**: Set `autovacuum_vacuum_scale_factor = 0.05` and `autovacuum_analyze_scale_factor = 0.02` for high-ingestion tables (`hazard_events`, `literature_chunks`).
- **Periodic Maintenance**: Run weekly `VACUUM ANALYZE` during low-traffic windows:
  ```bash
  docker compose exec postgres psql -U gaiaos -d gaiaos -c "VACUUM ANALYZE;"
  ```
- **PostGIS & Vector Reindexing**: Reindex GIST and HNSW indexes after massive dataset imports:
  ```bash
  docker compose exec postgres psql -U gaiaos -d gaiaos -c "REINDEX TABLE hazard_events; REINDEX TABLE literature_chunks;"
  ```

### Redis Operational Notes
- Redis is used for task queue state (RQ), rate limiting, and circuit breaker states (`gaiaos:circuit:*`).
- Configured with `appendonly yes` for durability.
- Ensure `maxmemory-policy noeviction` is active so task queue jobs are never evicted silently.

---

## 7. Single-Server VPS Deployment Guidance

- **Minimum Hardware Requirements**: 2 vCPU, 4GB RAM, 40GB SSD.
- **Resource Limits**:
  - `app`: 1.0 CPU, 512MB RAM
  - `worker`: 1.0 CPU, 512MB RAM
  - `postgres`: 1.0 CPU, 1GB RAM
- **UFW Firewall Rules**:
  ```bash
  ufw allow 80/tcp
  ufw allow 443/tcp
  ufw allow 22/tcp
  ufw enable
  ```
- **Caddy / Nginx SSL Reverse Proxy**: Route external HTTPS traffic to `localhost:8000`.

---

## 8. Troubleshooting Section

| Problem | Cause | Solution |
|---|---|---|
| `app` container crashing on boot | `db_migrations` failed or DB connection timeout | Check `docker compose logs db_migrations` and verify DB credentials |
| Circuit breaker open (`[degraded:source]`) | External public API rate limited or down | Check source status, wait for circuit recovery timeout (60s), or verify network egress |
| RQ Worker concurrency starvation | Too many heavy simulation jobs | Scale worker containers: `docker compose up -d --scale worker=4` |
