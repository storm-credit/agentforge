"""Sprint 1 runtime trace tables.

Revision ID: 0003_sprint1_runtime
Revises: 0002_sprint1_indexing
Create Date: 2026-05-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_sprint1_runtime"
down_revision: str | None = "0002_sprint1_indexing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("agent_id", sa.String(length=36), nullable=False),
        sa.Column("agent_version_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=120), nullable=False),
        sa.Column("user_department", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("input", sa.JSON(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("citations", sa.JSON(), nullable=False),
        sa.Column("guardrail", sa.JSON(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("retrieval_denied_count", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
        sa.ForeignKeyConstraint(["agent_version_id"], ["agent_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "run_steps",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("step_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("input_summary", sa.JSON(), nullable=False),
        sa.Column("output_summary", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "retrieval_hits",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("chunk_id", sa.String(length=220), nullable=True),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("citation_locator", sa.String(length=300), nullable=True),
        sa.Column("rank_original", sa.Integer(), nullable=False),
        sa.Column("rank_reranked", sa.Integer(), nullable=True),
        sa.Column("score_vector", sa.Float(), nullable=False),
        sa.Column("score_rerank", sa.Float(), nullable=True),
        sa.Column("used_in_context", sa.Boolean(), nullable=False),
        sa.Column("used_as_citation", sa.Boolean(), nullable=False),
        sa.Column("acl_filter_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["chunk_id"], ["document_chunks.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("retrieval_hits")
    op.drop_table("run_steps")
    op.drop_table("runs")
