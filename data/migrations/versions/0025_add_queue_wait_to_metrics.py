"""Add queue_wait_ms column to metrics table for P95 queue-wait scaling alerting.

Revision ID: 0025
Revises: 0024
Create Date: 2026-08-13 00:00:00.000000 UTC
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "metrics",
        sa.Column("queue_wait_ms", sa.Integer(), nullable=True, server_default=None),
    )


def downgrade() -> None:
    op.drop_column("metrics", "queue_wait_ms")
