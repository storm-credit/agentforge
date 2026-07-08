"""Persisted eval-harness runs.

Revision ID: 0004_eval_runs
Revises: 0003_sprint1_runtime
Create Date: 2026-07-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_eval_runs"
down_revision: str | None = "0003_sprint1_runtime"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "eval_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("corpus_id", sa.String(length=120), nullable=False),
        sa.Column("created_by", sa.String(length=120), nullable=False),
        sa.Column("label", sa.String(length=240), nullable=True),
        sa.Column("report", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("eval_runs")
