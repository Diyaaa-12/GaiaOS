# Runbook: Incident Response & Operational Triage

## 1. Overview & Triage Severity Levels
This runbook provides actionable, step-by-step procedures for operational incident triage, containment, and recovery in GaiaOS.

### Severity Definitions
| Severity Level | Definition | Response SLA | Examples |
| :--- | :--- | :--- | :--- |
| **SEV-1 (Critical)** | Core database loss, total API downtime, data corruption, or failed restore drill | Immediate (<15 mins) | Database crash, unhandled data corruption, worker pipeline failure |
| **SEV-2 (High)** | Degradation of key services, worker queue backlog, or partial data ingestion failure | <1 hour | NOAA/USGS external API rate limit, Redis cache eviction backlog |
| **SEV-3 (Moderate)** | Minor metric discrepancy or non-critical background task failure | Next business day | Telemetry logging lag, non-critical web-search tool failure |

---

## 2. Emergency Assessment Commands

### 2.1 Health Check & API Status
```bash
# Verify Gateway and core application health
curl -s http://localhost:8000/health | jq .
```

### 2.2 Database & Connection Pool Inspection
```bash
# Check PostgreSQL connection count and active queries
psql -U postgres -d gaiaos -c "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"
```

### 2.3 Redis & RQ Queue Inspection
```bash
# Check Redis memory usage and connected clients
redis-cli info memory

# Inspect RQ queue backlog
python -c "from redis import Redis; from rq import Queue; r = Redis(); q = Queue(connection=r); print('Jobs in queue:', len(q))"
```

---

## 3. Incident Containment & Mitigation Procedures

### Step 1: Isolate & Stop Faulty Worker Tasks
If a worker job is corrupting state or executing runaway retries:
```bash
# Pause worker container
docker compose stop worker
```

### Step 2: Enable Rate-Limiting & Gateway Protection
If hit by external traffic spike or denial-of-service:
```bash
# Set environment variables to enforce strict rate limiting
export ENABLE_RATE_LIMITING=true
export RATE_LIMIT_REQUESTS_PER_MINUTE=30
```

### Step 3: Trigger On-Demand Diagnostic Backup
Before attempting database remediation or host restart:
```bash
# Execute manual PostgreSQL backup job
python -c "import asyncio; from ops.backup.postgres_backup import run_postgres_backup; asyncio.run(run_postgres_backup())"
```

---

## 4. Communication & Incident Post-Mortem
1. **Notify On-Call Team**: Broadcast incident status to the internal engineering response channel.
2. **Track Discrepancies**: Log event IDs, affected investigation UUIDs, and timestamps.
3. **Post-Mortem**: Document root cause analysis, timeline, remediation actions, and action items in `docs/incidents/`.
