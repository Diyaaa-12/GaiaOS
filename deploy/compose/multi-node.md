# GaiaOS — Multi-VPS Docker Compose Reference Architecture

This reference guide describes how to deploy GaiaOS across multiple Virtual Private Servers (VPS) or physical host nodes using standard **Docker Compose**, without adopting Kubernetes.

> [!NOTE]
> Single-node Docker Compose ([`docker-compose.yml`](../../docker-compose.yml)) remains the primary, recommended default for individual developers, students, and single-server deployments. This multi-node guide is an optional reference path for deployers scaling worker capacity across multiple servers.

---

## 1. Network & Topology Overview

A multi-VPS deployment separates stateful data services from compute workers to allow horizontal worker scaling:

```
                  +------------------------------+
                  |    VPS 1: Data Services      |
                  |  - PostgreSQL (PostGIS)      |
                  |  - Redis 7                   |
                  +--------------+---------------+
                                 | Private Net / WireGuard (VPC)
         +-----------------------+-----------------------+
         |                                               |
+--------v---------------------+               +---------v--------------------+
|     VPS 2: API & UI          |               |   VPS 3+: Compute Workers    |
|  - GaiaOS App (Port 8000)    |               |  - Worker Nodes (1..N)      |
|  - Admin UI (Port 3000)      |               |  - Scheduler (Single active) |
|  - Alembic DB Migrations     |               +------------------------------+
+------------------------------+
```

### Network Assumptions
- All nodes communicate over a secure private network (VPC, private subnet, or encrypted WireGuard mesh VPN).
- Services on **VPS 1** (PostgreSQL/Redis) expose their ports only on the private network interface (e.g. `10.0.0.10`), never on public interfaces (`0.0.0.0`).

---

## 2. Server Configuration by Node Role

### Role A: Data Services (VPS 1 — `10.0.0.10`)

Run PostgreSQL (with PostGIS) and Redis.

**`docker-compose.data.yml`:**
```yaml
name: gaiaos-data

services:
  postgres:
    build:
      context: ../../infra/docker/postgres
      dockerfile: Dockerfile
    ports:
      - "10.0.0.10:5432:5432"
    environment:
      POSTGRES_USER: gaiaos
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?Required}
      POSTGRES_DB: gaiaos
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ../../infra/docker/postgres/init-extensions.sql:/docker-entrypoint-initdb.d/01-init-extensions.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U gaiaos -d gaiaos"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD:?Required}
    ports:
      - "10.0.0.10:6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
  redis_data:
```

---

### Role B: API & Admin UI Node (VPS 2 — `10.0.0.20`)

Run the FastAPI application server, execute schema migrations, and host the web admin UI.

**`docker-compose.api.yml`:**
```yaml
name: gaiaos-api

services:
  db_migrations:
    image: gaiaos/app:${GAIAOS_IMAGE_TAG:-v0.7.4}
    build:
      context: ../..
      dockerfile: Dockerfile
    command: alembic upgrade head
    environment:
      DATABASE_URL: postgresql://gaiaos:${POSTGRES_PASSWORD}@10.0.0.10:5432/gaiaos

  app:
    image: gaiaos/app:${GAIAOS_IMAGE_TAG:-v0.7.4}
    build:
      context: ../..
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      GAIAOS_ENV: prod
      LOG_LEVEL: INFO
      DATABASE_URL: postgresql://gaiaos:${POSTGRES_PASSWORD}@10.0.0.10:5432/gaiaos
      REDIS_URL: redis://:${REDIS_PASSWORD}@10.0.0.10:6379/0
      JWT_SECRET_KEY: ${JWT_SECRET_KEY:?Required}
      ENABLE_AUTH: "true"
      ENABLE_RATE_LIMITING: "true"
    depends_on:
      db_migrations:
        condition: service_completed_successfully

  admin_ui:
    image: gaiaos/admin-ui:${GAIAOS_IMAGE_TAG:-v0.7.4}
    build:
      context: ../../admin_ui
      dockerfile: Dockerfile.admin_ui
    ports:
      - "3000:80"
    depends_on:
      app:
        condition: service_healthy
```

---

### Role C: Worker Nodes (VPS 3+ — `10.0.0.30`, `10.0.0.31`, ...)

Run scale-out RQ background workers processing analysis tasks from Redis.

**`docker-compose.worker.yml`:**
```yaml
name: gaiaos-workers

services:
  worker:
    image: gaiaos/worker:${GAIAOS_IMAGE_TAG:-v0.7.4}
    build:
      context: ../..
      dockerfile: Dockerfile.worker
    environment:
      GAIAOS_ENV: prod
      LOG_LEVEL: INFO
      DATABASE_URL: postgresql://gaiaos:${POSTGRES_PASSWORD}@10.0.0.10:5432/gaiaos
      REDIS_URL: redis://:${REDIS_PASSWORD}@10.0.0.10:6379/0
      WORKER_POOL_SIZE: 4
      WORKER_CONCURRENCY_PER_PROCESS: 2

  scheduler:
    image: gaiaos/worker:${GAIAOS_IMAGE_TAG:-v0.7.4}
    build:
      context: ../..
      dockerfile: Dockerfile.worker
    command: python -m workers.scheduler
    environment:
      GAIAOS_ENV: prod
      LOG_LEVEL: INFO
      DATABASE_URL: postgresql://gaiaos:${POSTGRES_PASSWORD}@10.0.0.10:5432/gaiaos
      REDIS_URL: redis://:${REDIS_PASSWORD}@10.0.0.10:6379/0
```

---

## 3. Operational Best Practices & Hardening

1. **Firewall Isolation:**
   - Configure UFW / iptables on VPS 1 to only accept incoming traffic on ports 5432 and 6379 from VPS 2 (`10.0.0.20`) and VPS 3+ (`10.0.0.30/24`).
2. **PostgreSQL Connections:**
   - Adjust `max_connections` in PostgreSQL if running > 10 worker nodes to ensure connection pool capacity.
3. **Graceful Shutdown:**
   - Issue `docker compose stop -t 30 worker` on worker nodes during upgrades to allow active analysis jobs to finish or checkpoint.
