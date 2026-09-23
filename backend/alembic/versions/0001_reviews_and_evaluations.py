"""Reviews, review findings/test suggestions, and evaluation runs.

Revision ID: 0001
Revises:
Create Date: 2026-09-23 18:25:33.424771

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SEVERITIES = "'low', 'medium', 'high', 'critical'"


def upgrade() -> None:
    op.create_table(
        "reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("cache_key", sa.String(length=64), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("owner", sa.String(length=100), nullable=False),
        sa.Column("repo", sa.String(length=100), nullable=False),
        sa.Column("pull_number", sa.Integer(), nullable=False),
        sa.Column("head_sha", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=200), nullable=False),
        sa.Column("prompt_version", sa.String(length=50), nullable=False),
        sa.Column("review_config", postgresql.JSONB(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("risk_level", sa.String(length=16), nullable=True),
        sa.Column("finding_count", sa.Integer(), nullable=False),
        sa.Column("reviewed_files", postgresql.JSONB(), nullable=False),
        sa.Column("truncated_files", postgresql.JSONB(), nullable=False),
        sa.Column("skipped_files", postgresql.JSONB(), nullable=False),
        sa.Column("limitations", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(f"risk_level IN ({SEVERITIES})", name=op.f("ck_reviews_risk_level")),
        sa.CheckConstraint("pull_number > 0", name=op.f("ck_reviews_pull_number_positive")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reviews")),
    )
    # Cache identity: at most one reusable ("current") review per cache key.
    op.create_index(
        "uq_reviews_current_cache_key",
        "reviews",
        ["cache_key"],
        unique=True,
        postgresql_where=sa.text("is_current"),
    )
    op.create_index(
        "ix_reviews_repo_pull_created",
        "reviews",
        [
            sa.literal_column("lower(owner)"),
            sa.literal_column("lower(repo)"),
            "pull_number",
            sa.literal_column("created_at DESC"),
        ],
    )
    op.create_index("ix_reviews_created_at", "reviews", [sa.literal_column("created_at DESC")])

    op.create_table(
        "review_findings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("suggestion", sa.Text(), nullable=False),
        sa.Column("file", sa.Text(), nullable=True),
        sa.Column("line_start", sa.Integer(), nullable=True),
        sa.Column("line_end", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            f"severity IN ({SEVERITIES})", name=op.f("ck_review_findings_severity")
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name=op.f("ck_review_findings_confidence_range"),
        ),
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["reviews.id"],
            name=op.f("fk_review_findings_review_id_reviews"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_review_findings")),
        sa.UniqueConstraint(
            "review_id", "position", name="uq_review_findings_review_position"
        ),
    )
    op.create_index(
        op.f("ix_review_findings_review_id"), "review_findings", ["review_id"]
    )

    op.create_table(
        "review_test_suggestions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("file", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["reviews.id"],
            name=op.f("fk_review_test_suggestions_review_id_reviews"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_review_test_suggestions")),
        sa.UniqueConstraint(
            "review_id", "position", name="uq_review_test_suggestions_review_position"
        ),
    )
    op.create_index(
        op.f("ix_review_test_suggestions_review_id"), "review_test_suggestions", ["review_id"]
    )

    op.create_table(
        "evaluation_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=200), nullable=False),
        sa.Column("prompt_version", sa.String(length=50), nullable=False),
        sa.Column("review_config", postgresql.JSONB(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_cases", sa.Integer(), nullable=False),
        sa.Column("passed_cases", sa.Integer(), nullable=False),
        sa.Column("failed_cases", sa.Integer(), nullable=False),
        sa.Column("errored_cases", sa.Integer(), nullable=False),
        sa.Column("metrics", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evaluation_runs")),
    )
    op.create_index(op.f("ix_evaluation_runs_started_at"), "evaluation_runs", ["started_at"])

    op.create_table(
        "evaluation_case_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.String(length=100), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["evaluation_runs.id"],
            name=op.f("fk_evaluation_case_results_run_id_evaluation_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evaluation_case_results")),
        sa.UniqueConstraint(
            "run_id", "position", name="uq_evaluation_case_results_run_position"
        ),
    )
    op.create_index(
        op.f("ix_evaluation_case_results_run_id"), "evaluation_case_results", ["run_id"]
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_evaluation_case_results_run_id"), table_name="evaluation_case_results"
    )
    op.drop_table("evaluation_case_results")
    op.drop_index(op.f("ix_evaluation_runs_started_at"), table_name="evaluation_runs")
    op.drop_table("evaluation_runs")
    op.drop_index(
        op.f("ix_review_test_suggestions_review_id"), table_name="review_test_suggestions"
    )
    op.drop_table("review_test_suggestions")
    op.drop_index(op.f("ix_review_findings_review_id"), table_name="review_findings")
    op.drop_table("review_findings")
    op.drop_index("ix_reviews_created_at", table_name="reviews")
    op.drop_index("ix_reviews_repo_pull_created", table_name="reviews")
    op.drop_index("uq_reviews_current_cache_key", table_name="reviews")
    op.drop_table("reviews")
