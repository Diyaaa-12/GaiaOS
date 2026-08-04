# OpenStreetMap Administrative Boundary Resolution (Phase 6 — Milestone 3)

## Overview

GaiaOS Phase 6 Milestone 3 replaces crude point-radius spatial proximity matching (`ST_DWithin`) with real administrative boundary polygons (`ST_Within`) from OpenStreetMap (OSM).

Real regional reasoning (e.g. "earthquakes affecting the same province as this wildfire") requires exact administrative boundaries rather than arbitrary radial circles.

---

## Architectural Design

```
CausalChainAgent -> geocode(location) -> (lat, lon)
CausalChainAgent -> resolve_boundary(lat, lon)
                         │
                         ├─► Check Redis (gaiaos:cache:boundary:{lat}:{lon}, TTL 14 days)
                         ├─► Call Nominatim /reverse API via resilient_call(source="osm")
                         ├─► Upsert polygon into Postgres `administrative_boundaries` table
                         └─► Fallback to Postgres `ST_Within(point, geom)` query if Nominatim fails/misses
CausalChainAgent -> find_causal_chain_within_boundary(event_type, boundary_id)
                         │
                         └─► PostGIS SQL: WITH RECURSIVE ... WHERE ST_Within(he.region, boundary.geom)
                         │
                         └─► (If no boundary or 0 evidence) Automatic fallback to ST_DWithin radius query
```

---

## Configuration & Feature Flags

| Environment Variable | Settings Attribute | Default | Description |
| :--- | :--- | :--- | :--- |
| `ENABLE_BOUNDARY_REASONING` | `enable_boundary_reasoning` | `true` | Feature flag to enable/disable OSM boundary-matched causal reasoning. When false, immediately falls back to radius queries. |
| `NOMINATIM_API_URL` | `nominatim_api_url` | `https://nominatim.openstreetmap.org` | Base URL for Nominatim API service. |

---

## ADR-602: Self-Hosted Nominatim Path

- **Default Deployment**: GaiaOS defaults to the public Nominatim API (`https://nominatim.openstreetmap.org`) for low-volume development and free-first deployments.
- **Production / High-Volume Path**: High-volume deployments should run a self-hosted Nominatim Docker container (`mediagis/nominatim`). Switching to self-hosted Nominatim requires updating only `NOMINATIM_API_URL` in environment configuration, requiring zero code changes.

---

## OpenStreetMap Data License & Attribution

Administrative boundary polygon geometries are sourced from OpenStreetMap and licensed under the Open Database License (ODbL).

**Attribution Notice**:
> Data © OpenStreetMap contributors, licensed under the Open Data Commons Open Database License (ODbL).
