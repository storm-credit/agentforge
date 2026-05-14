"""Add model routing metadata to eval runs.

Revision ID: 0005_eval_model_routing
Revises: 0004_sprint1_eval_runs
Create Date: 2026-05-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_eval_model_routing"
down_revision: str | None = "0004_sprint1_eval_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "eval_runs",
        sa.Column(
            "model_routing_policy_ref",
            sa.String(length=240),
            nullable=False,
            server_default="packages/shared-contracts/model-routing-policy.v0.1.json",
        ),
    )
    op.add_column(
        "eval_runs",
        sa.Column("budget_class", sa.String(length=40), nullable=False, server_default="standard"),
    )
    op.add_column(
        "eval_runs",
        sa.Column("model_route_summary", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.alter_column("eval_runs", "model_routing_policy_ref", server_default=None)
    op.alter_column("eval_runs", "budget_class", server_default=None)
    op.alter_column("eval_runs", "model_route_summary", server_default=None)


def downgrade() -> None:
    op.drop_column("eval_runs", "model_route_summary")
    op.drop_column("eval_runs", "budget_class")
    op.drop_column("eval_runs", "model_routing_policy_ref")
