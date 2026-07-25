"""Migrate hazard_events.region to PostGIS GEOMETRY(Point, 4326) with GIST index.

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-24 00:00:00.000000 UTC
"""

from __future__ import annotations

import geoalchemy2
import sqlalchemy as sa
from alembic import op

from logging_config import get_logger
from tools.geocoding import LOCAL_GEOCODE_DB

_log = get_logger(__name__)

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add region_label column for human-readable location display
    op.add_column(
        "hazard_events",
        sa.Column("region_label", sa.String(), nullable=True),
    )

    # 2. Copy existing region string values into region_label
    op.execute("UPDATE hazard_events SET region_label = region;")

    # 3. Add temporary geometry column region_geom
    op.add_column(
        "hazard_events",
        sa.Column(
            "region_geom",
            geoalchemy2.types.Geometry(geometry_type="POINT", srid=4326),
            nullable=True,
        ),
    )

    # 4. Backfill region_geom using canonical coordinates from tools.geocoding.LOCAL_GEOCODE_DB
    # Unknown locations are left NULL (not silently mapped to Tokyo) and logged as skipped rows.
    for location, data in LOCAL_GEOCODE_DB.items():
        lat = data["lat"]
        lon = data["lon"]
        # Use parameterized ST_SetSRID(ST_MakePoint(lon, lat), 4326)
        op.execute(
            sa.text(
                "UPDATE hazard_events "
                "SET region_geom = ST_SetSRID(ST_MakePoint(:lon, :lat), 4326) "
                "WHERE LOWER(TRIM(region_label)) = :location;"
            ).bindparams(lon=lon, lat=lat, location=location.lower().strip())
        )

    # Log skipped/unresolved rows where region_geom is NULL
    conn = op.get_bind()
    unresolved_result = conn.execute(
        sa.text("SELECT id, region_label FROM hazard_events WHERE region_geom IS NULL;")
    )
    unresolved_rows = unresolved_result.fetchall()
    for row in unresolved_rows:
        _log.warning(
            "migration.0011.unresolved_region_geometry",
            event_id=str(row[0]),
            region_label=row[1],
        )

    # 5. Drop old string region index and column
    op.drop_index("ix_hazard_events_region", table_name="hazard_events")
    op.drop_column("hazard_events", "region")

    # 6. Rename region_geom to region
    op.alter_column("hazard_events", "region_geom", new_column_name="region")

    # 7. Create PostGIS GIST spatial index on hazard_events(region)
    op.create_index(
        "idx_hazard_events_region_gist",
        "hazard_events",
        ["region"],
        unique=False,
        postgresql_using="gist",
    )


def downgrade() -> None:
    # 1. Drop PostGIS GIST spatial index
    op.drop_index(
        "idx_hazard_events_region_gist",
        table_name="hazard_events",
        postgresql_using="gist",
    )

    # 2. Add temporary string column region_str
    op.add_column("hazard_events", sa.Column("region_str", sa.String(), nullable=True))

    # 3. Restore original string region strictly from region_label (without ST_AsText)
    op.execute("UPDATE hazard_events SET region_str = region_label;")

    # 4. Drop region geometry column
    op.drop_column("hazard_events", "region")

    # 5. Rename region_str back to region
    op.alter_column("hazard_events", "region_str", new_column_name="region")

    # 6. Recreate string index ix_hazard_events_region
    op.create_index("ix_hazard_events_region", "hazard_events", ["region"], unique=False)

    # 7. Drop region_label column
    op.drop_column("hazard_events", "region_label")
