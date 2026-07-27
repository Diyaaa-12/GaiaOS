"""Create backup_records and restore_drill_records tables.

Revision ID: 0017_backup_records
Revises: 0016_alert_rules_and_incidents
Create Date: 2026-07-27 19:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create enum type backup_status_enum
    backup_status_enum = postgresql.ENUM(
        "PENDING",
        "RUNNING",
        "SUCCESS",
        "FAILED",
        name="backup_status_enum",
    )
    backup_status_enum.create(op.get_bind(), checkfirst=True)

    # 2. Create backup_records table
    op.create_table(
        "backup_records",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("backup_id", sa.String(64), nullable=False, unique=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "PENDING",
                "RUNNING",
                "SUCCESS",
                "FAILED",
                name="backup_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("checksum", sa.String(64), nullable=False, server_default=""),
        sa.Column("storage_location", sa.String(512), nullable=False, server_default=""),
        sa.Column("postgres_version", sa.String(64), nullable=False, server_default=""),
        sa.Column("duration_ms", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("verification_metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("error_details", sa.Text(), nullable=True),
    )
    op.create_index("ix_backup_records_backup_id", "backup_records", ["backup_id"])
    op.create_index("ix_backup_records_status", "backup_records", ["status"])

    # 3. Create restore_drill_records table
    op.create_table(
        "restore_drill_records",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("drill_id", sa.String(64), nullable=False, unique=True),
        sa.Column("backup_id", sa.String(64), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "PENDING",
                "RUNNING",
                "SUCCESS",
                "FAILED",
                name="backup_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("duration_ms", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("row_counts_match", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("checksum_match", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("migration_version_match", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("discrepancies", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("error_details", sa.Text(), nullable=True),
    )
    op.create_index("ix_restore_drill_records_drill_id", "restore_drill_records", ["drill_id"])
    op.create_index("ix_restore_drill_records_backup_id", "restore_drill_records", ["backup_id"])
    op.create_index("ix_restore_drill_records_status", "restore_drill_records", ["status"])


def downgrade() -> None:
    op.drop_table("restore_drill_records")
    op.drop_table("backup_records")
    backup_status_enum = postgresql.ENUM(
        "PENDING",
        "RUNNING",
        "SUCCESS",
        "FAILED",
        name="backup_status_enum",
    )
    backup_status_enum.drop(op.get_bind(), checkfirst=True)
