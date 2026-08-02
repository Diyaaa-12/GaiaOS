"""Add slo_name column to alert_incidents table.

Revision ID: 0019
Revises: 0018
Create Date: 2026-08-03 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "alert_incidents",
        sa.Column("slo_name", sa.String(255), nullable=True),
    )
    op.create_index(
        "ix_alert_incidents_slo_name",
        "alert_incidents",
        ["slo_name"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_alert_incidents_slo_name", table_name="alert_incidents")
    op.drop_column("alert_incidents", "slo_name")
