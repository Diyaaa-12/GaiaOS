"""Create metrics table for raw observability event storage.

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-25 00:00:00.000000 UTC

This table stores the raw event rows emitted by metrics.collector.persist_metric().
Aggregation is computed on-demand by metrics.aggregation.aggregate_metrics().
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "metrics",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        # "JobCompleted" | "JobFailed" | "IngestionCompleted"
        sa.Column("event_type", sa.String(), nullable=False),
        # Stores complexity_tier for investigation jobs; source name for ingestion jobs;
        # NULL for JobFailed events that carry no tier context.
        # Reserved for future agent-level events (domain_agent group_by).
        sa.Column("group_key", sa.String(), nullable=True),
        # Job execution duration in milliseconds.
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        # LLM cost estimate in USD; 0.0 until real cost tracking is wired.
        sa.Column(
            "cost_estimate",
            sa.Numeric(precision=10, scale=6),
            nullable=False,
            server_default="0",
        ),
        # True for JobCompleted / IngestionCompleted; False for JobFailed.
        sa.Column("success", sa.Boolean(), nullable=False, server_default="true"),
        # Timestamp of the event; indexed for window queries.
        sa.Column(
            "ts",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_metrics_ts", "metrics", ["ts"], unique=False)
    op.create_index("ix_metrics_event_type", "metrics", ["event_type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_metrics_event_type", table_name="metrics")
    op.drop_index("ix_metrics_ts", table_name="metrics")
    op.drop_table("metrics")
