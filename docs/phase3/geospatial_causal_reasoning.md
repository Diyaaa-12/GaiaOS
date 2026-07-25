# Phase 3 Milestone 7 — PostGIS Geometry Migration for Hazard Events

## Overview

Milestone 7 migrates `hazard_events.region` from a plain string column to a PostGIS `GEOMETRY(Point, 4326)` column with a GIST spatial index. The causal-chain recursive traversal query is updated to perform radius-based spatial proximity matching using `ST_DWithin` in meters instead of exact string equality.

---

## 1. Resolution of Phase 2 Audit Finding

During the Phase 2 architecture audit, a primary finding highlighted that while PostGIS extensions were enabled in the PostgreSQL database, `hazard_events` matched queries using exact string equality (`WHERE region = 'Tokyo'`), failing to utilize PostGIS geospatial reasoning capabilities.

Milestone 7 closes this finding by:
- Converting `hazard_events.region` to a native `GEOMETRY(Point, 4326)` spatial column.
- Retaining human-readable display text in `region_label`.
- Creating a PostGIS GIST index (`idx_hazard_events_region_gist`) for index-accelerated spatial range queries.
- Updating `find_causal_chain()` to use `ST_DWithin` geography distance queries in meters.

---

## 2. Database Migration & Backfill Strategy (`0011_hazard_events_geometry.py`)

Alembic revision `0011_hazard_events_geometry.py` performs a zero-data-loss DDL & DML migration:

1. **Schema Addition**: Adds `region_label` (`VARCHAR`, nullable=True).
2. **Label Copy**: Copies existing string regions into `region_label` (`UPDATE hazard_events SET region_label = region;`).
3. **Geometry Backfill**: Backfills `region_geom` using canonical coordinates from `tools.geocoding.LOCAL_GEOCODE_DB` via `ST_SetSRID(ST_MakePoint(lon, lat), 4326)`. Unknown location strings are left `NULL` and logged as skipped rows.
4. **Column Swap**: Drops the old string `region` column and renames `region_geom` to `region`.
5. **GIST Index Creation**: Creates PostGIS GIST index `idx_hazard_events_region_gist` on `hazard_events(region)`.

---

## 3. Spatial Proximity Query (`ST_DWithin`)

`CausalChainRepository.find_causal_chain()` uses PostGIS `ST_DWithin` geography casting to filter events within the specified radius in meters:

```sql
WITH RECURSIVE causal_path AS (
    SELECT
        he.id AS event_id,
        he.event_type,
        he.region_label AS region,
        he.details,
        ARRAY[he.id] AS path_ids,
        ARRAY[he.event_type] AS path_types,
        1 AS depth,
        ARRAY[]::numeric[] AS edge_confidences
    FROM hazard_events he
    WHERE he.event_type = :event_type
      AND he.region IS NOT NULL
      AND ST_DWithin(
            he.region::geography,
            ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
            :radius_meters
          )
    ...
```

---

## 4. Configuration & Tool Reuse

- **Search Radius Setting**: Configured via `causal_chain_search_radius_meters` in `config/settings.py` (default: `50000.0` meters / 50 km, overridable via `CAUSAL_CHAIN_SEARCH_RADIUS_METERS`).
- **Geocoding Reuse**: `CausalChainAgent` reuses the existing `tools.geocoding.geocode_location` tool. On resolution failure, it returns an explicit error gap (`errors=["could not resolve region for causal analysis"]`) without crashing.
