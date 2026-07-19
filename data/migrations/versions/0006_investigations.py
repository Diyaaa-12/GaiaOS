"""Create investigations table and add foreign key to eval benchmark runs.

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-20 00:00:00.000000 UTC
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create investigations table
    op.create_table(
        "investigations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("complexity_tier", sa.String(), nullable=True),
        sa.Column("status", sa.String(), server_default="planning", nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column("execution_trace", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # 2. Create indices on investigations
    op.create_index(
        "ix_investigations_status",
        "investigations",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_investigations_created_at",
        "investigations",
        [sa.text("created_at DESC")],
        unique=False,
    )

    # 3. Add foreign key to eval_benchmark_runs
    op.create_foreign_key(
        "fk_eval_runs_investigation_id",
        "eval_benchmark_runs",
        "investigations",
        ["investigation_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # 1. Remove foreign key from eval_benchmark_runs
    op.drop_constraint(
        "fk_eval_runs_investigation_id",
        "eval_benchmark_runs",
        type_="foreignkey",
    )

    # 2. Drop indices
    op.drop_index("ix_investigations_created_at", table_name="investigations")
    op.drop_index("ix_investigations_status", table_name="investigations")

    # 3. Drop investigations table
    op.drop_table("investigations")
