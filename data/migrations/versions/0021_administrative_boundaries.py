"""Create administrative_boundaries table with PostGIS MultiPolygon geometry and GIST index.

Revision ID: 0021
Revises: 0020
Create Date: 2026-08-04 00:00:00.000000 UTC
"""

from __future__ import annotations

import geoalchemy2
import sqlalchemy as sa
from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create administrative_boundaries table
    op.create_table(
        "administrative_boundaries",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("osm_id", sa.String(), nullable=False, unique=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("admin_level", sa.Integer(), nullable=True),
        sa.Column(
            "geom",
            geoalchemy2.types.Geometry(geometry_type="MULTIPOLYGON", srid=4326),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_administrative_boundaries_osm_id",
        "administrative_boundaries",
        ["osm_id"],
        unique=True,
    )
    op.create_index(
        "ix_administrative_boundaries_name",
        "administrative_boundaries",
        ["name"],
        unique=False,
    )

    # 2. Create PostGIS GIST spatial index on administrative_boundaries(geom)
    op.create_index(
        "idx_admin_boundaries_geom_gist",
        "administrative_boundaries",
        ["geom"],
        unique=False,
        postgresql_using="gist",
    )


def downgrade() -> None:
    op.drop_index(
        "idx_admin_boundaries_geom_gist",
        table_name="administrative_boundaries",
        postgresql_using="gist",
    )
    op.drop_index("ix_administrative_boundaries_name", table_name="administrative_boundaries")
    op.drop_index("ix_administrative_boundaries_osm_id", table_name="administrative_boundaries")
    op.drop_table("administrative_boundaries")
