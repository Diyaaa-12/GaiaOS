"""OpenStreetMap Nominatim boundary resolution client wrapped with GaiaOS resilience layer."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

from sqlalchemy import text

from cache.client import get_redis
from cache.keys import RedisKeyBuilder
from config.settings import get_settings
from db.session import AsyncSessionLocal
from logging_config import get_logger
from resilience.degraded_mode import TTL_BY_SOURCE, ResilientResult, resilient_call
from tools.http_client import get_shared_client

_log = get_logger(__name__)


async def resolve_boundary(lat: float, lon: float) -> dict[str, Any] | None:
    """Resolve coordinates to an administrative boundary metadata dictionary.

    Execution flow:
    1. Check Redis boundary cache using 3-decimal coordinate key (~111m precision).
    2. Query Nominatim reverse API via resilience layer (resilient_call).
    3. On API success, upsert boundary into Postgres administrative_boundaries table,
       cache result in Redis, and return boundary metadata dict.
    4. On API failure/empty, fall back to checking if database contains an enclosing boundary
       via PostGIS ST_Within(point, geom).
    5. Return None if no boundary matches.
    """
    start_time = time.perf_counter()
    cache_key = RedisKeyBuilder.boundary_key(lat, lon)

    # 1. Check Redis cache
    boundary_data: dict[str, Any] | None = None

    try:
        redis_client = await get_redis()
        raw_cached = await redis_client.get(cache_key)
        if raw_cached:
            boundary_data = json.loads(raw_cached)
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            _log.info(
                "boundary_resolution.cache_hit",
                lat=lat,
                lon=lon,
                boundary_id=boundary_data.get("id"),
                name=boundary_data.get("name"),
                boundary_resolution_latency_ms=latency_ms,
            )
            return boundary_data
    except Exception as exc:
        _log.warning("boundary_resolution.cache_unavailable", error=str(exc))

    # 2. Query Nominatim reverse geocode via resilience layer
    settings = get_settings()
    base_url = settings.nominatim_api_url.rstrip("/")
    nominatim_cache_key = f"nominatim_reverse:{round(lat, 3)}:{round(lon, 3)}"

    async def _fetch_nominatim() -> dict[str, Any] | None:
        client = await get_shared_client()
        url = f"{base_url}/reverse"
        params = {
            "format": "jsonv2",
            "lat": str(lat),
            "lon": str(lon),
            "polygon_geojson": "1",
        }
        # Nominatim usage policy requires a descriptive User-Agent header.
        # https://operations.osmfoundation.org/policies/nominatim/
        resp = await client.get(
            url,
            params=params,
            headers={"User-Agent": "GaiaOS/0.5.4 (https://github.com/Diyaaa-12/GaiaOS)"},
        )
        if resp.status_code == 200:
            data = resp.json()
            if data and "osm_id" in data:
                return data
        resp.raise_for_status()
        return None

    result: ResilientResult[dict[str, Any] | None] = await resilient_call(
        source="osm",
        fn=_fetch_nominatim,
        cache_key=nominatim_cache_key,
        ttl=TTL_BY_SOURCE["osm"],
    )

    boundary_data = None

    # 3. Process Nominatim response if available
    if result.value is not None:
        raw_osm = result.value
        osm_type = raw_osm.get("osm_type", "relation")
        raw_osm_id = str(raw_osm.get("osm_id", ""))
        full_osm_id = f"{osm_type}/{raw_osm_id}"
        name = raw_osm.get("name") or raw_osm.get("display_name", "").split(",")[0] or "Unknown"
        admin_level = int(raw_osm.get("place_rank", 10))
        geojson = raw_osm.get("geojson")

        if geojson and AsyncSessionLocal is not None:
            geojson_str = json.dumps(geojson)
            boundary_uuid = uuid.uuid4()
            try:
                async with AsyncSessionLocal() as session:
                    stmt = text("""
                        INSERT INTO administrative_boundaries
                            (id, osm_id, name, admin_level, geom, created_at)
                        VALUES (
                            :id,
                            :osm_id,
                            :name,
                            :admin_level,
                            ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(:geojson), 4326)),
                            NOW()
                        )
                        ON CONFLICT (osm_id) DO UPDATE SET
                            name = EXCLUDED.name,
                            admin_level = EXCLUDED.admin_level,
                            geom = EXCLUDED.geom
                        RETURNING id, osm_id, name, admin_level;
                    """)
                    res = await session.execute(
                        stmt,
                        {
                            "id": boundary_uuid,
                            "osm_id": full_osm_id,
                            "name": name,
                            "admin_level": admin_level,
                            "geojson": geojson_str,
                        },
                    )
                    await session.commit()
                    row = res.fetchone()
                    if row:
                        boundary_data = {
                            "id": str(row[0]),
                            "osm_id": row[1],
                            "name": row[2],
                            "admin_level": row[3],
                        }
            except Exception as exc:
                _log.warning("boundary_resolution.upsert_failed", error=str(exc))

    # 4. Fallback: Query Postgres for existing enclosing boundary
    if boundary_data is None and AsyncSessionLocal is not None:
        try:
            async with AsyncSessionLocal() as session:
                stmt = text("""
                    SELECT id, osm_id, name, admin_level
                    FROM administrative_boundaries
                    WHERE ST_Within(
                        ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
                        geom
                    )
                    ORDER BY admin_level DESC
                    LIMIT 1;
                """)
                res = await session.execute(stmt, {"lat": lat, "lon": lon})
                row = res.fetchone()
                if row:
                    boundary_data = {
                        "id": str(row[0]),
                        "osm_id": row[1],
                        "name": row[2],
                        "admin_level": row[3],
                    }
                    _log.info(
                        "boundary_resolution.db_enclosing_match",
                        lat=lat,
                        lon=lon,
                        name=boundary_data["name"],
                    )
        except Exception as exc:
            _log.warning("boundary_resolution.db_fallback_failed", error=str(exc))

    latency_ms = int((time.perf_counter() - start_time) * 1000)

    # 5. Cache result if found
    if boundary_data:
        try:
            redis_client = await get_redis()
            await redis_client.set(cache_key, json.dumps(boundary_data), ex=TTL_BY_SOURCE["osm"])
        except Exception:
            pass

        _log.info(
            "boundary_resolution.success",
            lat=lat,
            lon=lon,
            boundary_id=boundary_data["id"],
            name=boundary_data["name"],
            boundary_resolution_latency_ms=latency_ms,
        )
        return boundary_data

    _log.info(
        "boundary_resolution.none_found",
        lat=lat,
        lon=lon,
        boundary_resolution_latency_ms=latency_ms,
    )
    return None
