"""Seed script to populate initial canonical administrative boundary polygons into Postgres/PostGIS.

Separated from Alembic migrations to keep schema migrations deterministic and fast.
Usage:
    python scripts/seed_administrative_boundaries.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from typing import Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config.settings import get_settings
from logging_config import get_logger

_log = get_logger(__name__)

# Canonical bounding box geometries converted to MultiPolygons for test regions.
# Format: [min_lon, min_lat, max_lon, max_lat]
CANONICAL_BOUNDARIES: list[dict[str, Any]] = [
    {
        "osm_id": "relation/7444",
        "name": "Paris",
        "admin_level": 8,
        "bbox": [2.224, 48.815, 2.47, 48.902],
    },
    {
        "osm_id": "relation/1543125",
        "name": "Tokyo",
        "admin_level": 4,
        "bbox": [139.56, 35.52, 139.91, 35.82],
    },
    {
        "osm_id": "relation/165475",
        "name": "California",
        "admin_level": 4,
        "bbox": [-124.409, 32.534, -114.131, 42.009],
    },
    {
        "osm_id": "relation/175342",
        "name": "London",
        "admin_level": 6,
        "bbox": [-0.351, 51.384, 0.148, 51.672],
    },
    {
        "osm_id": "relation/912940",
        "name": "Beijing",
        "admin_level": 4,
        "bbox": [116.1, 39.7, 116.7, 40.1],
    },
    {
        "osm_id": "relation/175905",
        "name": "New York",
        "admin_level": 4,
        "bbox": [-74.259, 40.477, -73.7, 40.917],
    },
    {
        "osm_id": "relation/280985",
        "name": "Madrid",
        "admin_level": 8,
        "bbox": [-3.834, 40.312, -3.525, 40.563],
    },
    {
        "osm_id": "relation/194389",
        "name": "Delhi",
        "admin_level": 4,
        "bbox": [77.019, 28.413, 77.348, 28.883],
    },
]


async def seed_boundaries() -> None:
    settings = get_settings()
    if not settings.database_url:
        _log.warning("seed_boundaries.skipped", reason="DATABASE_URL not set")
        return

    async_url = settings.asyncpg_url
    engine = create_async_engine(async_url)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        for b in CANONICAL_BOUNDARIES:
            min_lon, min_lat, max_lon, max_lat = b["bbox"]
            stmt = text("""
                INSERT INTO administrative_boundaries
                    (id, osm_id, name, admin_level, geom, created_at)
                VALUES (
                    :id,
                    :osm_id,
                    :name,
                    :admin_level,
                    ST_Multi(ST_SetSRID(
                        ST_MakeEnvelope(:min_lon, :min_lat, :max_lon, :max_lat),
                        4326)),
                    NOW()
                )
                ON CONFLICT (osm_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    admin_level = EXCLUDED.admin_level,
                    geom = EXCLUDED.geom;
            """)
            await session.execute(
                stmt,
                {
                    "id": uuid.uuid4(),
                    "osm_id": b["osm_id"],
                    "name": b["name"],
                    "admin_level": b["admin_level"],
                    "min_lon": min_lon,
                    "min_lat": min_lat,
                    "max_lon": max_lon,
                    "max_lat": max_lat,
                },
            )
        await session.commit()
        _log.info("seed_boundaries.completed", count=len(CANONICAL_BOUNDARIES))

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_boundaries())
