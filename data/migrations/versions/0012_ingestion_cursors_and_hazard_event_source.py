"""Create ingestion_cursors table and add source/external_id to hazard_events.

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-25 00:00:00.000000 UTC
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create ingestion_cursors table
    op.create_table(
        "ingestion_cursors",
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("last_ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("source"),
    )

    # 2. Add source and external_id columns to hazard_events
    op.add_column("hazard_events", sa.Column("source", sa.String(), nullable=True))
    op.add_column("hazard_events", sa.Column("external_id", sa.String(), nullable=True))

    # 3. Create indexes and unique constraint on hazard_events
    op.create_index("ix_hazard_events_source", "hazard_events", ["source"], unique=False)
    op.create_index("ix_hazard_events_external_id", "hazard_events", ["external_id"], unique=False)
    op.create_unique_constraint(
        "uq_hazard_event_source_external_id",
        "hazard_events",
        ["source", "external_id"],
    )


def downgrade() -> None:
    # 1. Drop unique constraint and indexes on hazard_events
    op.drop_constraint("uq_hazard_event_source_external_id", "hazard_events", type_="unique")
    op.drop_index("ix_hazard_events_external_id", table_name="hazard_events")
    op.drop_index("ix_hazard_events_source", table_name="hazard_events")

    # 2. Drop source and external_id columns from hazard_events
    op.drop_column("hazard_events", "external_id")
    op.drop_column("hazard_events", "source")

    # 3. Drop ingestion_cursors table
    op.drop_table("ingestion_cursors")
