"""Create eval benchmark questions and runs tables.

Revision ID: 0005
Revises: 0001
Create Date: 2026-07-20 00:00:00.000000 UTC
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "eval_benchmark_questions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("expected_domains", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("expected_complexity", sa.String(), nullable=False),
        sa.Column("reference_answer", sa.Text(), nullable=False),
        sa.Column("reference_evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "eval_benchmark_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("benchmark_question_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("investigation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("orchestrator_version", sa.String(), nullable=False),
        sa.Column("score", sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "run_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["benchmark_question_id"],
            ["eval_benchmark_questions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_eval_runs_version",
        "eval_benchmark_runs",
        ["orchestrator_version", sa.text("run_at DESC")],
        unique=False,
    )

    # Seed one hand-seeded question
    op.execute(
        """
        INSERT INTO eval_benchmark_questions (
            id, question_text, expected_domains,
            expected_complexity, reference_answer, reference_evidence
        )
        VALUES (
            'a0e0a0e0-a0e0-a0e0-a0e0-a0e0a0e0a0e0',
            'What are the PM2.5 and PM10 levels in Paris?',
            ARRAY['air_quality'],
            'trivial',
            'Paris air quality is good with PM2.5 at 12 ug/m3.',
            '{"source": "OpenAQ", "pm25": 12}'::jsonb
        );
        """
    )


def downgrade() -> None:
    op.drop_index("ix_eval_runs_version", table_name="eval_benchmark_runs")
    op.drop_table("eval_benchmark_runs")
    op.drop_table("eval_benchmark_questions")
