"""Add consent_public_research column to investigations table.

Revision ID: 0020
Revises: 0019
Create Date: 2026-08-03 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "investigations",
        sa.Column(
            "consent_public_research",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_index(
        "ix_investigations_consent_public_research",
        "investigations",
        ["consent_public_research"],
        unique=False,
    )
    op.create_index(
        "ix_investigations_status_created_at",
        "investigations",
        ["status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_investigations_status_created_at",
        table_name="investigations",
    )
    op.drop_index(
        "ix_investigations_consent_public_research",
        table_name="investigations",
    )
    op.drop_column("investigations", "consent_public_research")
