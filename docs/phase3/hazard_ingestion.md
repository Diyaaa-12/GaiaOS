# Phase 3 Milestone 8 — Real Hazard-Event Ingestion Pipeline

## Overview

Milestone 8 replaces hand-written fixture seed scripts with automated, scheduled ingestion of real historical hazard events (USGS Earthquakes and NOAA Ocean anomalies). It tracks ingestion progress in PostgreSQL (`ingestion_cursors`), enforces database-level deduplication via `(source, external_id)`, and executes recurring jobs via RQ Scheduler.

---

## 1. Source Field Mapping Specifications

### USGS Seismic Source (`usgs_historical.py`)
- **Source Identifier**: `"usgs"`
- **External ID**: `feature["id"]` (e.g., `"us7000test"`)
- **Event Type**: `"earthquake"`
- **Region Label**: `feature["properties"]["place"]`
- **Coordinates**: `(latitude, longitude)` from `feature["geometry"]["coordinates"]`
- **Event Date**: Parsed from epoch timestamp `feature["properties"]["time"]`
- **Details**: `Magnitude {mag} earthquake - {place}`

### NOAA Oceanographic Source (`noaa_historical.py`)
- **Source Identifier**: `"noaa"`
- **External ID**: `noaa_{station_id}_{timestamp}`
- **Event Type**: `"marine heatwave"`
- **Region Label**: Monitoring station city name
- **Coordinates**: Station latitude & longitude resolved from `LOCAL_GEOCODE_DB`
- **Event Date**: Timestamp from NOAA observations
- **Details**: `NOAA station {station_id} ({city}) water temperature: {temp}°C`

---

## 2. Ingestion Cursor Tracking & Persistence

Ingestion cursors are stored in PostgreSQL (`ingestion_cursors` table):

```sql
CREATE TABLE ingestion_cursors (
    source VARCHAR PRIMARY KEY,
    last_ingested_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL
);
```

### Max Event Date Advancement Rule
To ensure late-arriving upstream events are not missed, `last_ingested_at` advances strictly to `max(event_date)` among the ingested records from that run (never system clock `datetime.now()`). Cursor updates are performed atomically using PostgreSQL UPSERT:

```sql
INSERT INTO ingestion_cursors (source, last_ingested_at, updated_at)
VALUES (:source, :max_event_date, now())
ON CONFLICT (source) DO UPDATE
SET last_ingested_at = EXCLUDED.last_ingested_at,
    updated_at = now();
```

---

## 3. Database-Level Deduplication

`hazard_events` contains a unique constraint `uq_hazard_event_source_external_id` on `(source, external_id)`:

```sql
ALTER TABLE hazard_events
ADD CONSTRAINT uq_hazard_event_source_external_id UNIQUE (source, external_id);
```

During ingestion, records are inserted using `ON CONFLICT (source, external_id) DO NOTHING`. Re-ingesting existing events safely skips duplicates without throwing exceptions.

---

## 4. RQ Scheduler & Feature Flag Configuration

- **RQ Scheduler**: `workers/scheduler.py` runs as a persistent container service (`scheduler` in `docker-compose.yml`). On startup, it inspects Redis to detect active schedules, avoiding duplicate registrations.
- **Feature Flags**: Each pipeline can be toggled independently via environment variables in `config/settings.py`:
  - `ENABLE_USGS_INGESTION=true` (default `true`)
  - `ENABLE_NOAA_INGESTION=true` (default `true`)
  - `INGESTION_POLL_INTERVAL_HOURS=1` (default `1` hour)
