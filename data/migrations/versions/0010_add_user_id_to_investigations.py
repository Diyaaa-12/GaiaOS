"""Add user_id to investigations table.

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-23 00:00:00.000000 UTC
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "investigations",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_investigations_user_id_users",
        "investigations",
        "users",
        ["user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_investigations_user_id",
        "investigations",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_investigations_user_id", table_name="investigations")
    op.drop_constraint("fk_investigations_user_id_users", "investigations", type_="foreignkey")
    op.drop_column("investigations", "user_id")
