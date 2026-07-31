"""Create installed_plugins telemetry table.

Revision ID: 0018_installed_plugins
Revises: 0017
Create Date: 2026-07-31 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "installed_plugins",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("domain", sa.String(100), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("manifest_json", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "installed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index(
        "ix_installed_plugins_domain",
        "installed_plugins",
        ["domain"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_installed_plugins_domain", table_name="installed_plugins")
    op.drop_table("installed_plugins")
