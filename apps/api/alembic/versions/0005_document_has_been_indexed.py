"""Durable ``has_been_indexed`` marker on documents.

Adds ``documents.has_been_indexed``: a persistent boolean that is set True the first
time a document successfully reaches ``status = 'indexed'`` (in run_index_job) and is
NEVER reset afterward (not on index_failed, archive, or restore).

Why it exists (security): the reindex authorization gate in api/v1/knowledge.py must
require PRIVILEGED_ROLES for any document that has ever held trusted indexed content,
so a non-privileged co-reader cannot re-embed poison under the document's unchanged
ACL. Keying that gate on the volatile ``status == 'indexed'`` is unsafe because
run_index_job purges a document's vectors UNCONDITIONALLY and then, on any parse/upsert
failure, flips a previously-'indexed' document to 'index_failed'. In that state a
status-only gate silently stops applying -- the "index_failed side door". The durable
flag closes it. Third fix in the reindex trust-boundary family (PR #66, PR #83, this).

Backfill of existing rows (IMPORTANT): a plain ``server_default=false`` would mark every
existing row False, including documents that already hold trusted content -- re-exposing
exactly the poisoning this flag prevents. So upgrade() backfills has_been_indexed=True
for any document that has ever successfully indexed, using the two best signals available
in the current schema:
  1. ``status = 'indexed'``  -- documents that currently hold trusted content.
  2. a historical ``document.indexed`` audit event (audit_events, created in 0001) --
     documents that were indexed at least once but have since dropped to a non-'indexed'
     status (e.g. 'index_failed' after a failed reindex, or 'archived'). Signal (1) alone
     would miss precisely the side-door population this fix targets; the audit trail is the
     only durable record of past successful indexing, so we union it in.

Revision ID: 0005_document_has_been_indexed
Revises: 0004_eval_runs
Create Date: 2026-07-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_document_has_been_indexed"
down_revision: str | None = "0004_eval_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # server_default=false so existing rows get a concrete value under the NOT NULL
    # constraint; new inserts still get their value from the ORM default.
    op.add_column(
        "documents",
        sa.Column(
            "has_been_indexed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    # Backfill: mark as previously-trusted any document currently 'indexed' OR that has a
    # historical successful-index audit event. See module docstring for the reasoning.
    op.execute(
        """
        UPDATE documents
        SET has_been_indexed = true
        WHERE status = 'indexed'
           OR id IN (
               SELECT target_id FROM audit_events
               WHERE event_type = 'document.indexed'
           )
        """
    )


def downgrade() -> None:
    op.drop_column("documents", "has_been_indexed")
