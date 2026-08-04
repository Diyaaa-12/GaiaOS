"""Add source_id column to literature_chunks table.

Revision ID: 0022
Revises: 0021
Create Date: 2026-08-05 00:00:00.000000 UTC
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add source_id column
    op.add_column(
        "literature_chunks",
        sa.Column("source_id", sa.String(), nullable=True),
    )
    # Create index on source_id
    op.create_index(
        "ix_literature_chunks_source_id",
        "literature_chunks",
        ["source_id"],
        unique=False,
    )


def downgrade() -> None:
    # Drop index
    op.drop_index("ix_literature_chunks_source_id", table_name="literature_chunks")
    # Drop column
    op.drop_column("literature_chunks", "source_id")
