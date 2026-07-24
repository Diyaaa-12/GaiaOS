# GaiaOS Phase 3 — Milestone 4: Redis Operations (Persistence & Checkpoint TTL)

**Status:** Implemented and Verified  
**Component:** `orchestrator/graph/checkpointer.py` & `docker-compose.yml`  
**Persistence Engine:** Redis Append-Only File (AOF)  
**Eviction Strategy:** Native Key TTL (No custom cleanup background tasks)

---

## 1. Executive Summary

Phase 3 Milestone 4 hardens the Redis deployment supporting GaiaOS task execution and graph checkpointers by addressing two primary operational requirements:

1. **AOF Persistence:** Redis data is persisted across container restarts using Append-Only File (`appendonly yes`) logging backed by a dedicated Docker volume.
2. **Native Checkpoint TTL:** LangGraph execution checkpoints stored in Redis expire automatically using calculated native TTLs, preventing unbounded memory accumulation while guaranteeing checkpoints remain available throughout worst-case worker job execution and retries.

---

## 2. Redis AOF Persistence Configuration

### Container Specification (`docker-compose.yml`)
The Redis service is configured with AOF enabled and a persistent named volume:

```yaml
services:
  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5
      start_period: 5s

volumes:
  postgres_data:
  redis_data:
```

### Persistence Rationale & Tuning
- **Durability Role:** Redis stores task queue state (`rq`) and active LangGraph state checkpoints (`gaiaos:checkpoint:*`). Permanent investigation results, traces, and metadata remain stored durably in PostgreSQL (`investigations` table).
- **Default AOF Policy:** Uses Redis's default `appendfsync everysec`, balancing high write throughput with a maximum data loss window of 1 second in the event of an ungraceful host power failure.

---

## 3. Checkpoint TTL Sizing & Calculation Formula

### Architectural Role Separation
- **PostgreSQL (`investigations`):** Permanent, immutable record of completed and failed investigation runs.
- **Redis Checkpoints (`gaiaos:checkpoint:*`):** Ephemeral state required strictly for mid-investigation state transitions and worker crash recovery (`rq.Retry(max=2)`). Once an investigation finishes or exhausts retries, its Redis checkpoint is no longer required.

### Calculation Formula
The checkpoint TTL is computed dynamically from task queue execution parameters rather than using a hardcoded value:

$$\text{checkpoint\_ttl\_seconds} = \text{job\_timeout\_seconds} \times (\text{job\_max\_retries} + 1) \times \text{checkpoint\_ttl\_safety\_factor}$$

### Default Parameter Breakdown

| Settings Field | Env Variable Alias | Default Value | Description |
|---|---|---|---|
| `job_timeout_seconds` | `JOB_TIMEOUT_SECONDS` | `600` (10 min) | Max execution time allowed per single worker attempt. |
| `job_max_retries` | `JOB_MAX_RETRIES` | `2` | Max worker crash retries (total 3 attempts). |
| `checkpoint_ttl_safety_factor` | `CHECKPOINT_TTL_SAFETY_FACTOR` | `2.0` | Margin multiplier accounting for queuing delays & GC. |
| `checkpoint_ttl_seconds_override` | `CHECKPOINT_TTL_SECONDS` | `None` | Optional explicit override setting. |

### Calculated Default Value
$$\text{Worst-case job duration} = 600 \text{ seconds} \times (2 + 1) = 1800 \text{ seconds} (30 \text{ minutes})$$
$$\text{Default Checkpoint TTL} = 1800 \text{ seconds} \times 2.0 = 3600 \text{ seconds} (1 \text{ hour})$$

If `CHECKPOINT_TTL_SECONDS` is set in the environment, `Settings.checkpoint_ttl_seconds` returns the override value directly.

---

## 4. Key Lifecycle & Native Eviction

`RedisCheckpointSaver` applies `ex=self.ttl_seconds` on every `SET` operation:

1. **Checkpoint Key:** `gaiaos:checkpoint:{thread_id}:checkpoint:{checkpoint_id}`
2. **Latest Key:** `gaiaos:checkpoint:{thread_id}:latest`
3. **Pending Writes Key:** `gaiaos:checkpoint:{thread_id}:writes:{checkpoint_id}:{task_id}`

### Zero Maintenance Design
No background reaper, cron job, or custom abstraction is introduced. Key expiration is delegated entirely to Redis's native TTL eviction engine.
