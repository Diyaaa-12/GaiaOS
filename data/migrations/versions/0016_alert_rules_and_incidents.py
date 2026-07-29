"""Create alert_rules and alert_incidents tables for Phase 4 Milestone 3.

Revision ID: 0016
Revises: 0015
Create Date: 2026-07-26
"""

from __future__ import annotations

import alembic.op as op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# Revision identifiers, used by Alembic.
revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    # 1. Create alert_rules table
    op.create_table(
        "alert_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("metric", sa.String(length=255), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("comparison", sa.String(length=10), server_default="gt", nullable=False),
        sa.Column("window", sa.String(length=20), server_default="15m", nullable=False),
        sa.Column("severity", sa.String(length=20), server_default="warning", nullable=False),
        sa.Column("consecutive_cycles", sa.Integer(), server_default="1", nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_alert_rules_name"), "alert_rules", ["name"], unique=True)

    # 2. Create alert_incidents table
    op.create_table(
        "alert_incidents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rule_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("rule_name", sa.String(length=255), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="firing", nullable=False),
        sa.Column("last_value", sa.Float(), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("consecutive_violations", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "fired_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["rule_id"], ["alert_rules.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_alert_incidents_rule_id"), "alert_incidents", ["rule_id"], unique=False
    )
    op.create_index(
        op.f("ix_alert_incidents_rule_name"), "alert_incidents", ["rule_name"], unique=False
    )
    op.create_index(op.f("ix_alert_incidents_status"), "alert_incidents", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_alert_incidents_status"), table_name="alert_incidents")
    op.drop_index(op.f("ix_alert_incidents_rule_name"), table_name="alert_incidents")
    op.drop_index(op.f("ix_alert_incidents_rule_id"), table_name="alert_incidents")
    op.drop_table("alert_incidents")

    op.drop_index(op.f("ix_alert_rules_name"), table_name="alert_rules")
    op.drop_table("alert_rules")
