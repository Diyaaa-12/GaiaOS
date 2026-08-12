"""Create scaling_telemetry_samples table for worker scaling evidence (Phase 7 Audit Exit Fix).

Revision ID: 0024
Revises: 0023
Create Date: 2026-08-12 00:00:00.000000 UTC
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scaling_telemetry_samples",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("queue_depth", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("worker_utilization_pct", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("active_worker_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("busy_worker_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("recommended_pool_size", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "ts",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index(
        "ix_scaling_telemetry_samples_ts",
        "scaling_telemetry_samples",
        ["ts"],
    )


def downgrade() -> None:
    op.drop_index("ix_scaling_telemetry_samples_ts", table_name="scaling_telemetry_samples")
    op.drop_table("scaling_telemetry_samples")
