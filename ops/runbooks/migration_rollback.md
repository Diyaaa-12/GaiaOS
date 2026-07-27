# Runbook: Database Migration Rollback Procedure

## 1. Overview
This runbook details the exact, tested commands for rolling back PostgreSQL schema migrations using Alembic in GaiaOS.

---

## 2. Pre-Rollback Safety Checklist
Before executing any database schema downgrade:
- [ ] Confirm current active migration revision: `alembic current`
- [ ] Verify that a successful backup exists: `python -c "import asyncio; from ops.backup.postgres_backup import run_postgres_backup; asyncio.run(run_postgres_backup())"`
- [ ] Ensure application processes (`app`, `worker`) are temporarily paused to prevent concurrent writes during migration state transition.

---

## 3. Migration Rollback Commands

### 3.1 Inspect Migration History
```bash
# Check current migration revision
alembic current

# View history of applied migrations
alembic history --verbose
```

### 3.2 Single Revision Downgrade (Recommended)
Roll back exactly one schema revision (e.g. from `0017_backup_records` to `0016_alert_rules_and_incidents`):
```bash
alembic downgrade -1
```

### 3.3 Target Specific Revision Rollback
Roll back to a specific target revision code:
```bash
alembic downgrade 0016_alert_rules_and_incidents
```

---

## 4. Post-Rollback Verification

### Step 1: Verify Current Migration Version
```bash
alembic current
```
Output must display expected target revision ID (e.g. `0016_alert_rules_and_incidents`).

### Step 2: Verify Schema State
```bash
psql -U postgres -d gaiaos -c "\dt"
```

### Step 3: Run Internal Smoke Test Suite
```bash
pytest tests/test_db_connection.py tests/test_schemas.py
```

---

## 5. Emergency Recovery Procedure
If Alembic downgrade fails or enters an inconsistent state (`alembic_version` mismatch):
1. Force stamp Alembic version to known clean revision:
   ```bash
   alembic stamp <target_revision_id>
   ```
2. Restore database from latest clean backup if data loss occurred (refer to `ops/runbooks/disaster_recovery.md`).
