# Runbook: Full Disaster Recovery & Backup Restoration

## 1. Overview & Recovery Objectives
This runbook details the exact procedures for recovering PostgreSQL database states and Redis memory snapshots from cold backups during a critical infrastructure disaster (e.g. host crash, data corruption, or storage failure).

### Recovery Time & Point Objectives
- **RTO (Recovery Time Objective)**: < 30 minutes.
- **RPO (Recovery Point Objective)**: Max 24 hours (scheduled nightly backup) or last valid manual snapshot.

---

## 2. Encryption & Backup Security Assumptions
- **Local Storage Encryption**: Files stored under `BACKUP_STORAGE_PATH` (`./backups`) must reside on a LUKS/BitLocker encrypted volume.
- **Cloud Storage Encryption**: Object storage buckets must enforce provider-managed at-rest encryption (AWS SSE-S3/SSE-KMS or Azure Storage Encryption).

---

## 3. PostgreSQL Disaster Recovery Procedure

### Step 1: Locate Latest Successful Backup
```bash
# Query list of successful backups via Python CLI
python -c "import asyncio; from ops.backup.postgres_backup import LocalBackupStorage; storage = LocalBackupStorage(); print(asyncio.run(storage.list_backups()))"
```

### Step 2: Validate Backup Checksum
```bash
# Verify SHA256 checksum of target dump file
sha256sum ./backups/<backup_id>.sql
```

### Step 3: Restore Database Dump
```bash
# Terminate existing active connections to target database
psql -U postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'gaiaos' AND pid <> pg_backend_pid();"

# Drop and recreate production database
psql -U postgres -c "DROP DATABASE IF EXISTS gaiaos;"
psql -U postgres -c "CREATE DATABASE gaiaos;"

# Restore plain-text SQL dump
psql -U postgres -d gaiaos -f ./backups/<backup_id>.sql
```

### Step 4: Run Automated Restore Verification Drill
```bash
# Run restore drill tool to verify row counts, checksums, and Alembic version match
python -c "import asyncio; from ops.backup.restore_drill import run_restore_drill; print(asyncio.run(run_restore_drill()))"
```

---

## 4. Redis Memory Snapshot Recovery Procedure

### Step 1: Verify Redis RDB / AOF Snapshot Integrity
```bash
# Run automated Redis snapshot verification tool
python -c "from ops.backup.redis_backup import verify_redis_snapshot; print(verify_redis_snapshot('./data/dump.rdb'))"
```

### Step 2: Restore Redis Snapshot File
```bash
# Stop Redis container/service
docker compose stop redis

# Copy verified dump.rdb file into Redis data directory
cp ./backups/dump.rdb ./data/dump.rdb

# Restart Redis service
docker compose start redis
```

---

## 5. Post-Recovery Validation Checklist
- [ ] Run full system smoke tests: `pytest tests/test_db_connection.py`
- [ ] Verify API endpoints: `curl -s http://localhost:8000/api/v1/health`
- [ ] Verify background workers resume queue processing: `docker compose logs -f worker`
