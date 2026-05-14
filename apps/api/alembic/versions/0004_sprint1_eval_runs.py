"""Sprint 1 eval report tables.

Revision ID: 0004_sprint1_eval_runs
Revises: 0003_sprint1_runtime
Create Date: 2026-05-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_sprint1_eval_runs"
down_revision: str | None = "0003_sprint1_runtime"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "eval_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("corpus_id", sa.String(length=120), nullable=False),
        sa.Column("mode", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("total_cases", sa.Integer(), nullable=False),
        sa.Column("passed_cases", sa.Integer(), nullable=False),
        sa.Column("failed_cases", sa.Integer(), nullable=False),
        sa.Column("suite_counts", sa.JSON(), nullable=False),
        sa.Column("setup_findings", sa.JSON(), nullable=False),
        sa.Column("setup", sa.JSON(), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(length=120), nullable=False),
        sa.Column("approved_baseline_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_baseline_by", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "eval_case_results",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("eval_run_id", sa.String(length=36), nullable=False),
        sa.Column("case_id", sa.String(length=120), nullable=False),
        sa.Column("suite", sa.String(length=80), nullable=False),
        sa.Column("expected_behavior", sa.String(length=80), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("findings", sa.JSON(), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=True),
        sa.Column("citation_document_ids", sa.JSON(), nullable=False),
        sa.Column("retrieval_document_ids", sa.JSON(), nullable=False),
        sa.Column("retrieval_denied_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["eval_run_id"], ["eval_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_eval_case_results_eval_run_id",
        "eval_case_results",
        ["eval_run_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_eval_case_results_eval_run_id", table_name="eval_case_results")
    op.drop_table("eval_case_results")
    op.drop_table("eval_runs")
