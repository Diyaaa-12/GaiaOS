# Single-Node Metrics Aggregation & OpenMetrics Exposition — Phase 7 Milestone 6

**Status:** Completed (Single-Node Metrics Retained; Multi-Host Aggregation Deferred under M5 Outcome B)  
**Target:** GaiaOS Admin Observability API & Prometheus Integration  

---

## 1. Overview & Architectural Scope

Phase 7 Milestone 6 completes the metrics aggregation and OpenMetrics exposition layer for single-node GaiaOS deployments.

Per the conditional scope established in `Roadmap_Phase7.md` §171 following Milestone 5's Outcome B verdict (which concluded multi-node physical scaling is currently unneeded), multi-host distributed Prometheus scraping across remote worker instances is explicitly deferred. Single-node PostgreSQL event aggregation and OpenMetrics endpoint exposition provide complete, performant observability without introducing unneeded infrastructure complexity.

---

## 2. Metrics Data Flow & SQL Aggregation Engine

### 2.1 Event Emission & Persistence
1. Worker jobs and API operations emit structured `MetricEvent` subclasses via `metrics.collector.emit()`.
2. Raw event rows are persisted to the PostgreSQL `metrics` table via `metrics.collector.persist_metric()`.
3. Event types include:
   - `JobCompleted` / `JobFailed` (graph investigation jobs)
   - `IngestionCompleted` (data ingestion pipeline executions)
   - `BackupCompleted` / `RestoreDrillCompleted` / `RestoreDrillFailed` (maintenance operations)
   - `CalibrationCompleted` (simulation model calibration runs)
   - `PlannerRegionHintMissing` / `LocationRegexFallbackExecuted` (agent execution diagnostics)

### 2.2 Aggregation Engine (`metrics/aggregation.py`)
`aggregate_metrics(session, window, group_by, event_type=None)` computes windowed percentile latency, cost, and success rate rollups using parameterized SQL queries:

- **Supported Time Windows**: `"1d"`, `"7d"`, `"30d"`, `"90d"`.
- **Supported GroupBy Dimensions**:
  - `GroupBy.COMPLEXITY_TIER` (`"complexity_tier"`): Groups investigation jobs by complexity tier (`"trivial"`, `"moderate"`, `"complex"`).
  - `GroupBy.DAY` (`"day"`): Groups metric events by calendar day (UTC) via `DATE_TRUNC('day', ts)`.
  - `GroupBy.EVENT_TYPE` (`"event_type"`): Groups raw rows by event type (`"JobCompleted"`, `"IngestionCompleted"`, etc.).
- **Event Type Filtering**: Optional `event_type` parameter filters queries to a specific validated domain event type (`SUPPORTED_EVENT_TYPES`), preventing metric pollution between short ingestion tasks and long investigation graph executions.

---

## 3. Administration REST API (`GET /api/v1/admin/metrics`)

### Endpoint Details
```http
GET /api/v1/admin/metrics?window=7d&group_by=complexity_tier&event_type=JobCompleted
```
- **Access Control**: Requires `Role.ADMIN`. Non-admin requests receive HTTP 403.
- **Validation**: `window`, `group_by`, and `event_type` are strictly validated against domain enumerations; unrecognised parameters return HTTP 422.

### JSON Response Schema
```json
{
  "generated_at": "2026-08-10T00:57:00.000000+00:00",
  "window": "7d",
  "group_by": "complexity_tier",
  "event_type": "JobCompleted",
  "rollups": [
    {
      "group_key": "moderate",
      "count": 42,
      "p50_latency_ms": 1250.0,
      "p95_latency_ms": 3400.0,
      "avg_cost_estimate": 0.0,
      "success_rate": 0.976
    }
  ],
  "queue_depth": 0,
  "worker_utilization_pct": 0.0,
  "recommended_pool_size": 2
}
```

---

## 4. OpenMetrics / Prometheus Exposition Endpoint

### Endpoint Details
```http
GET /api/v1/admin/metrics/prometheus
```
- **Authentication**: Supports static scraper token via `PROMETHEUS_METRICS_TOKEN` environment variable (`Authorization: Bearer <token>` or `X-Prometheus-Token: <token>`), or standard ADMIN JWT authentication.

### OpenMetrics Text Format Output
```text
# HELP gaiaos_planner_region_hint_missing_total Missing region_hint before fallback count
# TYPE gaiaos_planner_region_hint_missing_total counter
gaiaos_planner_region_hint_missing_total{agent="seismic"} 0

# HELP gaiaos_location_regex_fallback_total Location regex fallback execution count
# TYPE gaiaos_location_regex_fallback_total counter
gaiaos_location_regex_fallback_total{agent="seismic"} 0

# HELP gaiaos_circuit_breaker_state Circuit breaker status gauge (0=closed, 0.5=half-open, 1=open)
# TYPE gaiaos_circuit_breaker_state gauge
gaiaos_circuit_breaker_state{source="usgs"} 0.0
gaiaos_circuit_breaker_state{source="noaa"} 0.0
gaiaos_circuit_breaker_state{source="copernicus"} 0.0
gaiaos_circuit_breaker_state{source="era5"} 0.0
gaiaos_circuit_breaker_state{source="gdelt"} 0.0
gaiaos_circuit_breaker_state{source="arxiv"} 0.0

# HELP gaiaos_queue_depth Current RQ task queue depth
# TYPE gaiaos_queue_depth gauge
gaiaos_queue_depth 0

# HELP gaiaos_worker_utilization_pct Current worker utilization percentage
# TYPE gaiaos_worker_utilization_pct gauge
gaiaos_worker_utilization_pct 0.0

# HELP gaiaos_recommended_pool_size Recommended RQ worker pool size
# TYPE gaiaos_recommended_pool_size gauge
gaiaos_recommended_pool_size 2
```

---

## 5. Verification & Testing

Verify metrics aggregation and OpenMetrics endpoints using pytest:
```bash
python -m pytest -v tests/test_admin_metrics_endpoint.py
```
All integration test cases verify role authorization, parameter validation (HTTP 422), event_type filtering, timestamp presence, and OpenMetrics circuit breaker gauge rendering.
