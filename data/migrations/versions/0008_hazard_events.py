"""Create hazard_events and hazard_relationships tables.

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-21 00:00:00.000000 UTC
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create hazard_events table
    op.create_table(
        "hazard_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("region", sa.String(), nullable=False),
        sa.Column("event_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # 2. Create indices on hazard_events
    op.create_index(
        "ix_hazard_events_event_type",
        "hazard_events",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        "ix_hazard_events_region",
        "hazard_events",
        ["region"],
        unique=False,
    )

    # 3. Create hazard_relationships table
    op.create_table(
        "hazard_relationships",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("child_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("relationship_type", sa.String(), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=3, scale=2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["parent_id"], ["hazard_events.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["child_id"], ["hazard_events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "parent_id", "child_id", "relationship_type", name="uq_parent_child_rel"
        ),
    )

    # 4. Create indices on hazard_relationships
    op.create_index(
        "ix_hazard_relationships_parent_id",
        "hazard_relationships",
        ["parent_id"],
        unique=False,
    )
    op.create_index(
        "ix_hazard_relationships_child_id",
        "hazard_relationships",
        ["child_id"],
        unique=False,
    )


def downgrade() -> None:
    # 1. Drop indices
    op.drop_index("ix_hazard_relationships_child_id", table_name="hazard_relationships")
    op.drop_index("ix_hazard_relationships_parent_id", table_name="hazard_relationships")

    # 2. Drop hazard_relationships table
    op.drop_table("hazard_relationships")

    # 3. Drop indices on hazard_events
    op.drop_index("ix_hazard_events_region", table_name="hazard_events")
    op.drop_index("ix_hazard_events_event_type", table_name="hazard_events")

    # 4. Drop hazard_events table
    op.drop_table("hazard_events")
