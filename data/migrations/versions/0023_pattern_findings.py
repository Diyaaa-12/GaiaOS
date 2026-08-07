"""Create pattern_findings table for longitudinal pattern mining (Phase 7 Milestone 2).

Revision ID: 0023
Revises: 0022
Create Date: 2026-08-07 00:00:00.000000 UTC
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pattern_findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("pattern_hash", sa.String(length=64), nullable=False),
        sa.Column("algorithm_version", sa.String(length=16), nullable=False, server_default="1.0"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("source_event_type", sa.String(), nullable=False),
        sa.Column("target_event_type", sa.String(), nullable=False),
        sa.Column("region_label", sa.String(), nullable=True),
        sa.Column("time_window_days", sa.Integer(), nullable=False),
        sa.Column("support_count", sa.Integer(), nullable=False),
        sa.Column("total_source_events", sa.Integer(), nullable=False),
        sa.Column("total_target_events", sa.Integer(), nullable=False),
        sa.Column("observed_rate", sa.Float(), nullable=False),
        sa.Column("baseline_rate", sa.Float(), nullable=False),
        sa.Column("lift", sa.Float(), nullable=False),
        sa.Column("statistical_confidence", sa.Float(), nullable=False),
        sa.Column("uncertainty", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("supporting_event_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("mined_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Indexes
    op.create_index("ix_pattern_findings_pattern_hash", "pattern_findings", ["pattern_hash"])
    op.create_index(
        "ix_pattern_findings_active_confidence",
        "pattern_findings",
        ["is_active", "statistical_confidence"],
    )
    op.create_index(
        "ix_pattern_findings_source_event_type",
        "pattern_findings",
        ["source_event_type"],
    )
    op.create_index(
        "ix_pattern_findings_target_event_type",
        "pattern_findings",
        ["target_event_type"],
    )
    op.create_index("ix_pattern_findings_region_label", "pattern_findings", ["region_label"])


def downgrade() -> None:
    op.drop_index("ix_pattern_findings_region_label", table_name="pattern_findings")
    op.drop_index("ix_pattern_findings_target_event_type", table_name="pattern_findings")
    op.drop_index("ix_pattern_findings_source_event_type", table_name="pattern_findings")
    op.drop_index("ix_pattern_findings_active_confidence", table_name="pattern_findings")
    op.drop_index("ix_pattern_findings_pattern_hash", table_name="pattern_findings")
    op.drop_table("pattern_findings")
