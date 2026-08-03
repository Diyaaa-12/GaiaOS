# Phase 6 Data Sources Reference

**Milestone 2 Expansion** — Multi-Source Environmental Data Ingestion

---

## Overview

GaiaOS Phase 6 Milestone 2 expands automated, scheduled hazard event ingestion from the original 2 sources (USGS, NOAA) to 5 total sources by integrating Copernicus Sentinel satellite product metadata, ERA5 atmospheric reanalysis baselines, and GDELT socio-political hazard news events.

All ingestion pipelines execute under the unified ingestion framework established in Phase 3 Milestone 8:
- Idempotent deduplication via PostgreSQL `ON CONFLICT (source, external_id) DO NOTHING`.
- Monotonic cursor tracking via `ingestion_cursors`.
- Network resilience, retry, and circuit breaking via Milestone 1's `resilient_call()`.
- Source attribution metadata preserved in `HazardEventRecord.details`.

---

## Source Inventory

| Source | Domain / Focus | Provider | Resilience TTL | Event Type | Primary Bounding / Filters |
|---|---|---|---|---|---|
| `usgs` | Seismic Events | USGS Earthquake API | 600 s (10m) | `earthquake` | Global / Minimum Magnitude 2.5 |
| `noaa` | Oceanographic / Marine | NOAA CO-OPS API | 900 s (15m) | `marine heatwave` | Key Coastal Ocean Stations |
| `copernicus` | Satellite Wildfire Metadata | EU Copernicus Data Space | 1800 s (30m) | `wildfire_satellite` | Bounding Box Sentinel-2 OData |
| `era5` | Atmospheric Reanalysis Baseline | ECMWF / ERA5 Archive | 3600 s (1h) | `atmospheric_anomaly` | Daily Mean Temp, Max Wind, Precip |
| `gdelt` | Socio-Political Hazard Context | GDELT DOC 2.0 API | 900 s (15m) | `civil_unrest_hazard_adjacent` | Global News Query Filter & Max Cap |

---

## Detailed Data Source Specifications

### 1. Copernicus Sentinel Satellite Metadata (`copernicus`)
- **API Endpoint:** `https://catalogue.dataspace.copernicus.eu/odata/v1/Products`
- **Authentication:** Public OData catalogue endpoint (no API key required).
- **Ingestion Mapping:**
  - `external_id`: `copernicus_{Id}`
  - `event_type`: `wildfire_satellite`
  - `details`: Contains product name, provider name ("EU Copernicus Data Space"), original product ID, and direct OData product URL.
- **Attribution Terms:** Free and open access under the EU Copernicus Programme terms.

### 2. ERA5 Atmospheric Reanalysis (`era5`)
- **API Endpoint:** `https://archive-api.open-meteo.com/v1/archive`
- **Authentication:** Free public API endpoint.
- **Ingestion Mapping:**
  - `external_id`: `era5_{location}_{date}`
  - `event_type`: `atmospheric_anomaly`
  - `details`: Contains daily mean temperature (°C), daily max wind speed (km/h), daily precipitation sum (mm), provider name ("ECMWF ERA5"), and source URL.
- **Attribution Terms:** Generated using Copernicus Climate Change Service information (ECMWF ERA5).

### 3. GDELT Socio-Political Hazard News Events (`gdelt`)
- **API Endpoint:** `https://api.gdeltproject.org/api/v2/doc/doc`
- **Authentication:** Open public API (no API key required).
- **Ingestion Mapping:**
  - `external_id`: `gdelt_{sha256(url)[:16]}`
  - `event_type`: `civil_unrest_hazard_adjacent`
  - `details`: Contains article title, domain, provider name ("GDELT Project"), language, and direct article URL.
- **Attribution Terms:** Open data provided by The GDELT Project. Text derived from GDELT is framed as untrusted web content before LLM prompt inclusion.

---

## Operational Settings & Feature Flags

| Setting Key | Environment Variable | Default | Description |
|---|---|---|---|
| `enable_copernicus_ingestion` | `ENABLE_COPERNICUS_INGESTION` | `true` | Feature flag for Copernicus ingestion job |
| `enable_era5_ingestion` | `ENABLE_ERA5_INGESTION` | `true` | Feature flag for ERA5 ingestion job |
| `enable_gdelt_ingestion` | `ENABLE_GDELT_INGESTION` | `true` | Feature flag for GDELT ingestion job |
| `gdelt_max_records_per_run` | `GDELT_MAX_RECORDS_PER_RUN` | `250` | Maximum GDELT records ingested per run |
| `copernicus_api_url` | `COPERNICUS_API_URL` | Copernicus OData URL | Base URL for Copernicus OData API |
| `era5_api_url` | `ERA5_API_URL` | Open-Meteo Archive URL | Base URL for ERA5 reanalysis API |
| `gdelt_api_url` | `GDELT_API_URL` | GDELT DOC 2.0 URL | Base URL for GDELT DOC 2.0 API |

---

## Architectural & Data Flow Summary

```
Scheduler (RQ Scheduler)
    └── run_ingestion_job(source) ["usgs", "noaa", "copernicus", "era5", "gdelt"]
         ├── Check Feature Flag (ENABLE_{SOURCE}_INGESTION)
         ├── Query Postgres ingestion_cursors -> last_ingested_at
         ├── Tool Client (resilient_call -> get_shared_client())
         │     └── Retries, Circuit Breaker, Degraded Cache Fallback
         ├── Adapter: fetch_recent_{source}_events(since)
         │     └── Maps raw JSON/OData -> HazardEventRecord (with details attribution)
         ├── Postgres DB Writer:
         │     ├── INSERT INTO hazard_events ON CONFLICT DO NOTHING
         │     └── UPSERT ingestion_cursors SET last_ingested_at = max(event_date)
         └── Telemetry: emit(IngestionCompleted) & persist_metric()
```
