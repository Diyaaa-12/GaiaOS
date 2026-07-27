# GaiaOS Phase 4 — Geocoding & Tool-Client Data Quality

## 1. Overview
Milestone 5 addresses two long-standing technical debt items identified during Phase 2 and 3 audits:
1. **Dynamic NOAA Ocean Station Resolution**: Replaced the legacy hardcoded ocean station fallback (`8518750`) with dynamic station lookup via NOAA's station metadata API.
2. **Process-Lifetime Shared HTTP Client**: Replaced unpooled, per-call `httpx.AsyncClient()` instantiations across all tool clients with a process-lifetime singleton factory (`tools/http_client.py`).

---

## 2. Shared HTTP Client Lifecycle (`tools/http_client.py`)

### 2.1 Factory API
- **`get_shared_client() -> httpx.AsyncClient`**: Lazily initializes a single `httpx.AsyncClient` instance reused by all tool clients under `tools/`.
- **`close_shared_client() -> None`**: Closes the shared client cleanly during shutdown. Idempotent and safe for multiple calls.

### 2.2 Lifespan & Migration
- Integrated `close_shared_client()` into the FastAPI lifespan shutdown hook (`app/main.py`).
- Every tool client under `tools/` (`geocoding`, `air_quality_openaq`, `ocean_noaa`, `seismic_usgs`, `weather`, `wildfire_firms`) obtains its client exclusively via `get_shared_client()`.

---

## 3. Dynamic NOAA Station Lookup & Caching

### 3.1 Resolution Algorithm & Topology
```
Location String
      ↓
geocode_location() -> (lat, lon)
      ↓
resolve_nearest_station(lat, lon, network="noaa")
      ↓
  Redis Cache Hit? ─── YES ───► Return Cached Station ID
      │ NO
      ▼
NOAA Station Metadata API (stations.json)
      ↓
Haversine Great-Circle Distance Comparison
      ↓
Distance <= MAX_STATION_DISTANCE_KM (500.0 km)?
  ├── YES ──► Cache in Redis (30-day TTL) & Return station_id
  └── NO  ──► Return None (Explicit Error Gap)
```

### 3.2 Redis Caching Strategy
- **Key Namespace**: `RedisKeyBuilder.station_key(lat, lon, network="noaa")`
- **Key Format**: `gaiaos:cache:station:noaa:{round_lat}:{round_lon}`
- **Spatial Resolution**: Coordinates rounded to 2 decimal places ($2\text{ decimal places} \approx 1.11\text{ km}$ resolution at the equator), balancing cache key reuse against geographic accuracy.
- **TTL**: 30 days (`2,592,000` seconds).
- **Observability**: Logs `station_lookup.cache_hit` and `station_lookup.cache_miss`.

### 3.3 Fail-Fast Policy in `OceanAgent`
- If `station_id` is `None` (no station within 500 km or NOAA Metadata API failure), `OceanAgent` fails fast by returning an explicit gap in `output.errors` without attempting a downstream NOAA ocean measurement fetch. Hardcoded station fallbacks are strictly eliminated.
