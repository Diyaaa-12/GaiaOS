# GaiaOS — Optional Kubernetes & k3s Deployment Guide

This guide details the **dev-verified, optional Kubernetes deployment path** for GaiaOS using Helm and k3s.

> [!IMPORTANT]
> **Deployment Priority & Non-Production Disclaimer (ADR-802):**
> - **Primary Default:** Single-node Docker Compose ([`docker-compose.yml`](../../docker-compose.yml)) remains the standard, recommended, student-first deployment path for GaiaOS.
> - **Optional & Dev-Verified:** The Kubernetes deployment path described here is explicitly optional, dev-verified only, and designed for testing or local development on lightweight clusters such as `k3s`.
> - **Non-Goals:** This deployment model does **NOT** include Horizontal Pod Autoscaling (HPA), multi-cluster federation, managed cloud Kubernetes dependencies, or production SLA claims.

---

## 1. Architecture Overview

The GaiaOS Helm chart (`deploy/helm/gaiaos/`) packages application compute components while connecting to external or self-hosted PostgreSQL (PostGIS enabled) and Redis data stores:

```
                      +------------------------------------------+
                      |         External Data Layer              |
                      |  - PostgreSQL 16 + PostGIS + pgvector   |
                      |  - Redis 7                               |
                      +--------------------+---------------------+
                                           |
    +--------------------------------------+--------------------------------------+
    |                                      |                                      |
+---v--------------------------------------v--------------------------------------v---+
|  GaiaOS Helm Release Namespace (`gaiaos`)                                           |
|                                                                                      |
|  +---------------------+  +---------------------+  +-----------------------------+  |
|  |  `app` Deployment   |  | `worker` Deployment |  |    `scheduler` Deployment   |  |
|  |  (FastAPI, 2 Replicas|  | (RQ Workers, 2 Rep) |  |   (Single Active Instance)  |  |
|  +----------+----------+  +---------------------+  +-----------------------------+  |
|             |                                                                        |
|  +----------v----------+                                                             |
|  | `admin-ui` Deploy   |   +------------------------------------------------------+  |
|  | (React / Nginx)     |   | `db-migrations` Pre-Install / Pre-Upgrade Job Hook  |  |
|  +---------------------+   +------------------------------------------------------+  |
+--------------------------------------------------------------------------------------+
```

---

## 2. Prerequisites

1. **Lightweight Kubernetes Cluster:** `k3s` (recommended for local dev verification), `k3d`, `minikube`, or MicroK8s.
2. **Tools:** `kubectl` and `helm` (v3+).
3. **Database Dependencies:**
   - PostgreSQL server with PostGIS (`postgis`) and pgvector (`vector`) extensions enabled.
   - Redis server (v7+).

---

## 3. Quickstart Deployment Guide

### Step 1: Create Namespace
```bash
kubectl create namespace gaiaos
```

### Step 2: Build & Import Container Images (Local k3s)
If using locally built images without a remote container registry:

```bash
# Build images
docker build -t gaiaos/app:v0.7.4 -f Dockerfile .
docker build -t gaiaos/worker:v0.7.4 -f Dockerfile.worker .
docker build -t gaiaos/scheduler:v0.7.4 -f Dockerfile.worker .
docker build -t gaiaos/admin-ui:v0.7.4 -f admin_ui/Dockerfile.admin_ui admin_ui/

# Import into k3s image store
sudo k3s ctr images import gaiaos-app.tar  # or via k3d image load
```

### Step 3: Configure Database & Secret Values
Create a custom `values-override.yaml` file with your database connection strings and security keys:

```yaml
# values-override.yaml
global:
  environment: dev
  logLevel: INFO

image:
  app:
    tag: "v0.7.4"
  worker:
    tag: "v0.7.4"
  scheduler:
    tag: "v0.7.4"
  adminUi:
    tag: "v0.7.4"

externalDatabase:
  url: "postgresql://gaiaos:your_secure_password@postgres-service.default.svc.cluster.local:5432/gaiaos"

externalRedis:
  url: "redis://redis-service.default.svc.cluster.local:6379/0"

auth:
  jwtSecretKey: "your-at-least-32-character-long-secret-key"
  enableAuth: true
  enableRateLimiting: true
```

### Step 4: Install Helm Release
Deploy GaiaOS into your cluster:

```bash
helm install gaiaos deploy/helm/gaiaos -n gaiaos -f values-override.yaml
```

The Helm release automatically triggers the pre-install database migration Job (`alembic upgrade head`) before bringing up the application, worker, and admin UI deployments.

### Step 5: Verify Deployment Status
Check migration completion and pod readiness:

```bash
# Verify migration job completed
kubectl get jobs -n gaiaos

# Verify pod status
kubectl get pods -n gaiaos
```

Output:
```
NAME                                   READY   STATUS      RESTARTS   AGE
gaiaos-db-migrations-x8q2z             0/1     Completed   0          45s
gaiaos-app-6d8b9484b9-2k7p9            1/1     Running     0          30s
gaiaos-app-6d8b9484b9-m4n8x            1/1     Running     0          30s
gaiaos-worker-5c9946bc77-h7z9l         1/1     Running     0          30s
gaiaos-worker-5c9946bc77-w2v1p         1/1     Running     0          30s
gaiaos-scheduler-789f4b9d6c-j9k2l      1/1     Running     0          30s
gaiaos-admin-ui-7d9b9944f-p5x4q        1/1     Running     0          30s
```

---

## 4. Accessing Services & Local Verification

By default, all Services are created with `type: ClusterIP` for security isolation.

Access the FastAPI application locally using `kubectl port-forward`:

```bash
kubectl port-forward svc/gaiaos-app 8000:8000 -n gaiaos
```

Test application live healthcheck:
```bash
curl http://localhost:8000/api/v1/health/live
```

Execute live worker task smoke verification:
```bash
SMOKE_BASE_URL=http://localhost:8000 python -m tests.test_worker_image_smoke
```

---

## 5. Upgrade & Cleanup

### Upgrade Release
```bash
helm upgrade gaiaos deploy/helm/gaiaos -n gaiaos -f values-override.yaml
```

### Uninstall Release
```bash
helm uninstall gaiaos -n gaiaos
```
