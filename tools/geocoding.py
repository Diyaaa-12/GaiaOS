"""Geocoding helper using Open-Meteo geocoding API, local city fallback,
and dynamic NOAA station resolution.
"""

from __future__ import annotations

import math
from typing import Any

from cache.client import get_redis
from cache.keys import RedisKeyBuilder
from config.settings import get_settings
from logging_config import get_logger
from resilience.degraded_mode import TTL_BY_SOURCE, ResilientResult, resilient_call
from tools.http_client import get_shared_client

_log = get_logger(__name__)

# NOAA CO-OPS Metadata API endpoint for active ocean stations
NOAA_STATIONS_API_URL = "https://api.tidesandcurrents.noaa.gov/mdapi/v1.0/webapi/stations.json"

# Maximum search radius in km for coastal ocean station relevance.
# 500 km balances regional coastal station coverage while rejecting distant inland queries.
MAX_STATION_DISTANCE_KM = 500.0

# Local geocoding fallback database for common locations to accelerate tests
LOCAL_GEOCODE_DB: dict[str, dict[str, Any]] = {
    "paris": {
        "lat": 48.8566,
        "lon": 2.3522,
        "bbox": [2.224, 48.815, 2.47, 48.902],
    },
    "beijing": {
        "lat": 39.9042,
        "lon": 116.4074,
        "bbox": [116.1, 39.7, 116.7, 40.1],
    },
    "london": {
        "lat": 51.5074,
        "lon": -0.1278,
        "bbox": [-0.351, 51.384, 0.148, 51.672],
    },
    "delhi": {
        "lat": 28.6139,
        "lon": 77.209,
        "bbox": [77.019, 28.413, 77.348, 28.883],
    },
    "madrid": {
        "lat": 40.4168,
        "lon": -3.7038,
        "bbox": [-3.834, 40.312, -3.525, 40.563],
    },
    "tokyo": {
        "lat": 35.6762,
        "lon": 139.6503,
        "bbox": [139.56, 35.52, 139.91, 35.82],
    },
    "california": {
        "lat": 36.7783,
        "lon": -119.4179,
        "bbox": [-124.409, 32.534, -114.131, 42.009],
    },
    "new york": {
        "lat": 40.7128,
        "lon": -74.006,
        "bbox": [-74.259, 40.477, -73.7, 40.917],
    },
    "miami": {
        "lat": 25.7617,
        "lon": -80.1918,
        "bbox": [-80.32, 25.70, -80.13, 25.85],
    },
    "san francisco": {
        "lat": 37.7749,
        "lon": -122.4194,
        "bbox": [-122.52, 37.70, -122.35, 37.83],
    },
}


def _haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points on Earth in kilometers."""
    r = 6371.0  # Earth radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


async def resolve_nearest_station(lat: float, lon: float, network: str = "noaa") -> str | None:
    """Dynamically resolve nearest ocean station ID for given coordinates.

    Checks Redis cache first using rounded coordinates (~1.11 km spatial resolution).
    If cache misses, queries the station metadata API (via resilience layer) and
    calculates the closest station within MAX_STATION_DISTANCE_KM.
    Caches successful results for 30 days (2,592,000s).
    Returns None if no station is within range or if the station API call fails.
    """
    cache_key = RedisKeyBuilder.station_key(lat, lon, network)

    # 1. Check Redis cache
    try:
        redis_client = await get_redis()
        cached_id = await redis_client.get(cache_key)
        if cached_id:
            _log.info(
                "station_lookup.cache_hit",
                lat=lat,
                lon=lon,
                network=network,
                station_id=cached_id,
            )
            return str(cached_id)
        _log.info("station_lookup.cache_miss", lat=lat, lon=lon, network=network)
    except Exception as exc:
        _log.warning("station_lookup.cache_unavailable", error=str(exc))

    # 2. Query station metadata API via resilience layer
    station_cache_key = f"stations_metadata:{network}"

    async def _fetch_stations() -> list[dict[str, Any]]:
        client = await get_shared_client()
        resp = await client.get(NOAA_STATIONS_API_URL)
        if resp.status_code != 200:
            _log.error("station_lookup.failed", status=resp.status_code)
            resp.raise_for_status()
        data = resp.json()
        return data.get("stations", [])  # type: ignore[no-any-return]

    result: ResilientResult[list[dict[str, Any]]] = await resilient_call(
        source="noaa",
        fn=_fetch_stations,
        cache_key=station_cache_key,
        ttl=TTL_BY_SOURCE["noaa"],
    )

    if result.value is None:
        _log.warning("station_lookup.api_unavailable", lat=lat, lon=lon, network=network)
        return None

    stations = result.value

    # 3. Find nearest station within MAX_STATION_DISTANCE_KM
    nearest_id: str | None = None
    min_dist = float("inf")

    for st in stations:
        try:
            st_lat = float(st["lat"])
            st_lon = float(st.get("lng", st.get("lon", 0.0)))
            dist = _haversine_distance_km(lat, lon, st_lat, st_lon)
            if dist < min_dist and dist <= MAX_STATION_DISTANCE_KM:
                min_dist = dist
                nearest_id = str(st["id"])
        except (KeyError, ValueError, TypeError):
            continue

    # 4. Cache result if found
    if nearest_id:
        try:
            redis_client = await get_redis()
            await redis_client.set(cache_key, nearest_id, ex=2592000)
        except Exception:
            pass
        return nearest_id

    _log.warning("station_lookup.no_nearby_station", lat=lat, lon=lon, network=network)
    return None


async def geocode_location(location: str) -> dict[str, Any]:
    """Resolve location name to latitude, longitude, bounding box, and dynamic ocean station_id.

    Queries Open-Meteo Geocoding API (via resilience layer) first, with a local
    city database fallback.  Coordinates are then passed to resolve_nearest_station
    to dynamically determine the nearest active NOAA ocean station.
    """
    loc_clean = location.strip().lower()
    geo_data: dict[str, Any] | None = None

    # 1. Try calling Open-Meteo Geocoding API via resilience layer
    settings = get_settings()
    url = settings.open_meteo_geocoding_url
    geocode_cache_key = f"geocode:{loc_clean}"

    async def _fetch_geocode() -> dict[str, Any] | None:
        client = await get_shared_client()
        resp = await client.get(url, params={"name": location, "count": 1})
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            if results:
                res = results[0]
                lat = res.get("latitude")
                lon = res.get("longitude")
                bbox = [lon - 0.5, lat - 0.5, lon + 0.5, lat + 0.5]
                _log.info("geocoding.api_success", location=location, lat=lat, lon=lon)
                return {"lat": lat, "lon": lon, "bbox": bbox}
        resp.raise_for_status()
        return None  # unreachable but satisfies type checker

    result: ResilientResult[dict[str, Any] | None] = await resilient_call(
        source="geocoding",
        fn=_fetch_geocode,
        cache_key=geocode_cache_key,
        ttl=TTL_BY_SOURCE["geocoding"],
    )

    if result.value is not None:
        geo_data = result.value
        if result.degraded:
            _log.info("geocoding.serving_cached", location=location)

    # 2. Local fallback database for common locations
    if geo_data is None:
        if loc_clean in LOCAL_GEOCODE_DB:
            _log.info("geocoding.local_match_fallback", location=location)
            match = LOCAL_GEOCODE_DB[loc_clean]
            geo_data = {"lat": match["lat"], "lon": match["lon"], "bbox": match["bbox"]}

    if geo_data is None:
        _log.warning("geocoding.failed", location=location)
        raise ValueError(f"Geocoding failed for unknown location: '{location}'")

    # 3. Dynamically resolve nearest ocean station
    station_id = await resolve_nearest_station(geo_data["lat"], geo_data["lon"])
    geo_data["station_id"] = station_id
    return geo_data
