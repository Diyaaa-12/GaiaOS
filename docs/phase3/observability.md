# GaiaOS — Operational Observability (Phase 3 Milestone 9)

## What This Is

This document describes GaiaOS's **operational observability metrics** — what the system
tracks, how it tracks it, and what to expect from the `/api/v1/admin/metrics` endpoint.

This is **distinct** from the evaluation harness's reasoning-quality metrics (Milestone 5).
The two systems are related but serve different purposes:

| System | Purpose | Storage | Query path |
|--------|---------|---------|-----------|
| **M5 eval harness** | Benchmark reasoning quality against ground-truth answers | `eval_benchmark_runs` table | `eval/harness/` |
| **M9 observability** | Operational latency, throughput, and cost per job | `metrics` table | `GET /admin/metrics` |

Do not conflate them. The eval harness tells you *whether the system answers correctly*.
Observability tells you *how long it takes and how much it costs*.

---

## What Is Tracked

The following event types are persisted to the `metrics` table:

### `JobCompleted`
Emitted by `workers/jobs/investigation_job.py` when an investigation job finishes
successfully.

| Column | Value |
|--------|-------|
| `event_type` | `"JobCompleted"` |
| `group_key` | `complexity_tier` (`"trivial"`, `"moderate"`, `"complex"`, or `NULL` if not set) |
| `duration_ms` | Job wall-clock time in milliseconds |
| `cost_estimate` | `0.0` — see "Cost tracking" below |
| `success` | `TRUE` |

### `JobFailed`
Emitted by `workers/jobs/investigation_job.py` only on **terminal failure** (retries
exhausted), not on transient retry attempts.

| Column | Value |
|--------|-------|
| `event_type` | `"JobFailed"` |
| `group_key` | `NULL` |
| `duration_ms` | `0` |
| `cost_estimate` | `0.0` |
| `success` | `FALSE` |

### `IngestionCompleted`
Emitted by `workers/jobs/ingestion_jobs.py` after each scheduled USGS/NOAA ingestion job.

| Column | Value |
|--------|-------|
| `event_type` | `"IngestionCompleted"` |
| `group_key` | Source name: `"usgs"` or `"noaa"` |
| `duration_ms` | Ingestion job wall-clock time in milliseconds |
| `cost_estimate` | `0.0` (ingestion jobs have no LLM cost) |
| `success` | `TRUE` on success |

---

## Cost Tracking

`avg_cost_estimate` in every `MetricRollup` is currently `0.0`. The `JobCompleted.llm_cost_estimate`
field exists but is never populated with a real value — the graph nodes do not yet report
token usage or cost back to the worker job. This will be addressed when LLM cost tracking
is wired into the graph synthesis layer.

---

## API

```
GET /api/v1/admin/metrics?window=7d&group_by=complexity_tier
Authorization: Bearer <admin-jwt>
```

### Parameters

| Parameter | Type | Allowed values | Default |
|-----------|------|---------------|---------|
| `window` | string | `1d`, `7d`, `30d`, `90d` | `7d` |
| `group_by` | string | `complexity_tier`, `day` | `complexity_tier` |

### Response

```json
{
  "window": "7d",
  "group_by": "complexity_tier",
  "rollups": [
    {
      "group_key": null,
      "count": 42,
      "p50_latency_ms": 1234.5,
      "p95_latency_ms": 8901.2,
      "avg_cost_estimate": 0.0,
      "success_rate": 0.976
    }
  ]
}
```

An **empty `rollups` list** is returned when no data exists in the requested window
(e.g. freshly deployed system). This is a valid response, not an error.

### Access Control

Requires `Role.ADMIN`. Non-admin requests return `403 Forbidden`.

---

## Database

Raw events are stored in the `metrics` table (migration `0013_metrics.py`):

```sql
metrics (
    id            UUID PRIMARY KEY,
    event_type    VARCHAR NOT NULL,
    group_key     VARCHAR,
    duration_ms   INTEGER NOT NULL DEFAULT 0,
    cost_estimate NUMERIC(10,6) NOT NULL DEFAULT 0,
    success       BOOLEAN NOT NULL DEFAULT TRUE,
    ts            TIMESTAMPTZ NOT NULL DEFAULT now()
)
```

Indexes: `ix_metrics_ts` (for window queries), `ix_metrics_event_type`.

Rows are **never updated or deleted** — they are append-only. The aggregation layer
reads them on-demand; there is no pre-computed rollup cache.
