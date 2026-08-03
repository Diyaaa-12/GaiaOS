# Resilience Layer

**Phase 6 Milestone 1** — `resilience/`

---

## Overview

Every external tool call in GaiaOS now routes through a shared resilience layer
that provides three guarantees:

1. **Retry** — up to 3 attempts with exponential backoff and jitter before giving up.
2. **Circuit breaking** — if a source is consistently failing, the circuit opens and
   live attempts are skipped to protect the source and reduce latency.
3. **Degraded-mode fallback** — on failure, the last-known-good cached response is
   served with an explicit `degraded=True` flag and an informational error string in
   `AgentOutput.errors`, rather than failing the investigation outright.

This is in-process, application-level resilience — not a service mesh or sidecar
proxy, matching the project's consistent preference for the simplest correct mechanism.

---

## Data Flow

```
Agent → tool client → resilient_call(source, fn, cache_key)
    → circuit_breaker.is_open(source)?
        YES → _serve_from_cache(source, redis_key)
              → cache hit  → ResilientResult(value, degraded=True,  "cached")
              → cache miss → ResilientResult(None,  degraded=True,  "unavailable")
        NO  → retry fn() up to 3 attempts (exponential backoff, jitter)
              → success    → cache result
                           → ResilientResult(value, degraded=False, "live")
              → exhausted  → record_failure(source)
                           → _serve_from_cache → "cached" or "unavailable"
```

---

## Per-Source TTL Table

| Source       | Redis TTL | Rationale |
|---|---|---|
| `usgs`       | 600 s (10 min)   | Seismic feeds update frequently |
| `noaa`       | 900 s (15 min)   | Ocean readings update hourly |
| `open_meteo` | 300 s (5 min)    | Weather data is highly time-sensitive |
| `firms`      | 300 s (5 min)    | Active fire data should be as fresh as possible |
| `openaq`     | 600 s (10 min)   | Air-quality measurements update hourly at most |
| `geocoding`  | 86400 s (24 h)   | City coordinates change essentially never |

> **Note:** administrative boundary data (M3, OSM) will use a long TTL (weeks)
> when it is added as a source.

---

## Circuit Breaker State Machine

```
              N consecutive failures
   CLOSED ──────────────────────────────► OPEN
     ▲                                     │
     │  probe success                      │  timeout elapsed
     │                                     ▼
     └───────────────────────────── HALF-OPEN ──► OPEN (probe failure)
```

- **Threshold** (`CIRCUIT_FAILURE_THRESHOLD`, default 5): consecutive failures before opening.
- **Timeout** (`CIRCUIT_HALF_OPEN_TIMEOUT_S`, default 60 s): seconds before a probe is allowed.
- State is stored in Redis (`gaiaos:circuit:{source}`) and is shared across all worker replicas.

---

## Redis Key Namespaces

| Purpose | Pattern | Builder method |
|---|---|---|
| Circuit state | `gaiaos:circuit:{source}` | `RedisKeyBuilder.circuit_key(source)` |
| Response cache | `gaiaos:cache:{source}:{key}` | `RedisKeyBuilder.source_cache_key(source, key)` |

Both use the existing `get_redis()` client. No new Redis connection pool is created.

---

## `ResilientResult` Schema

```python
@dataclass
class ResilientResult(Generic[T]):
    value: T | None                          # None when source unavailable, no cache
    degraded: bool                           # True when value is stale or absent
    source_status: "live" | "cached" | "unavailable"
```

Agents unpack the result like this:

```python
result = await client.get_water_temperature(station_id)
if result.degraded:
    errors.append(f"[degraded:noaa] {result.source_status} — serving stale data")
data = result.value or {}
```

---

## Observability

Three new metric events are emitted (see `metrics/events.py`):

| Event | When |
|---|---|
| `CircuitStateChanged` | Any state transition (closed→open, open→half-open, etc.) |
| `CacheHit` | A cached response is served instead of a live one |
| `DegradedResponseEmitted` | An agent receives a degraded result |

These are natural additions to the Phase 4 admin dashboard — no new infrastructure.

---

## Security Note

Cached responses must respect the same trust boundary as live ones. A cached
evidence item still flows through Synthesis's untrusted-data prompt framing (Phase 3).
The `degraded` flag does not change the evidence's trust level — it only signals
staleness. Do not assume "it's cached" means "it's safe."

---

## Rollback

Set `RESILIENCE_BYPASS=true` to revert to bare Phase 5 tool-call behaviour (no retry,
no circuit breaker, no cache fallback). For dev/test only — do not enable in staging
or production.

---

## Settings Reference

| Variable | Default | Description |
|---|---|---|
| `RESILIENCE_BYPASS` | `false` | Bypass all resilience logic |
| `CIRCUIT_FAILURE_THRESHOLD` | `5` | Consecutive failures before circuit opens |
| `CIRCUIT_HALF_OPEN_TIMEOUT_S` | `60` | Seconds before probe is allowed after open |

---

## Scalability Note

Circuit-breaker state is Redis-backed specifically so it is shared correctly across
horizontally-scaled workers (Phase 5 M7). A worker-local-only breaker would let each
replica independently hammer a down source.

---

## Future Notes

- Every Phase 6 milestone from M2 onward routes new tool clients through this layer by
  default, not as an afterthought.
- The `TTL_BY_SOURCE` table in `resilience/degraded_mode.py` is the single place to
  add TTLs for new sources.
- OSM boundary data (M3) should use a weeks-long TTL given how rarely boundaries change.
