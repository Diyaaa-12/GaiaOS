"""Create literature_chunks table with vector and GIN search indices.

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-20 00:00:00.000000 UTC
"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from config.settings import get_settings

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    settings = get_settings()
    dim = settings.embedding_dimension

    # 1. Create literature_chunks table
    op.create_table(
        "literature_chunks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("document_id", sa.Text(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(dim), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "ts_content",
            postgresql.TSVECTOR,
            sa.Computed("to_tsvector('english', chunk_text)", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # 2. Create indices
    op.create_index(
        "ix_literature_chunks_document",
        "literature_chunks",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        "ix_literature_chunks_fts",
        "literature_chunks",
        ["ts_content"],
        postgresql_using="gin",
    )

    # pgvector HNSW index
    op.execute(
        "CREATE INDEX ix_literature_chunks_embedding ON literature_chunks "
        "USING hnsw (embedding vector_cosine_ops);"
    )


def downgrade() -> None:
    # 1. Drop indices
    op.drop_index("ix_literature_chunks_fts", table_name="literature_chunks")
    op.drop_index("ix_literature_chunks_document", table_name="literature_chunks")
    op.execute("DROP INDEX IF EXISTS ix_literature_chunks_embedding;")

    # 2. Drop table
    op.drop_table("literature_chunks")
