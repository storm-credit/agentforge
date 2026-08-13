"""Source-level classification defaults + per-document classification provenance.

WO-2026-08-13-SOURCE-ACL-DEFAULTS-001 (SEC-010, SEC-011). Four columns, no new tables, no
change to any existing row's data.

WHAT IS ADDED

``knowledge_sources.default_access_groups`` (JSON, NOT NULL, default ``[]``)
    The administrator-configured group default a new document inherits when its own request
    specifies none. ``[]`` means NOT CONFIGURED, which is why every existing row can be given
    that value without changing anything: a source with no configured group default falls
    through to the endpoint's own platform fallback, exactly as before this column existed.
    Its sibling ``default_confidentiality_level`` has existed since 0001 and needed no schema
    change -- it was simply never read by document creation, which is the dead-feature half of
    this Work Order.

``documents.confidentiality_source`` / ``documents.access_groups_source`` (String(40), NOT
NULL, default ``'unknown'``)
    Where each half of the document's classification came from: ``explicit`` |
    ``source_default`` | ``platform_default`` | ``unknown``.

``documents.classification_source_id`` (String(36), NULL)
    The knowledge source whose defaults were applied, or NULL when nothing was inherited.
    Deliberately NOT a foreign key: it is a provenance snapshot of what was applied, not a
    live relationship. ``knowledge_source_id`` already carries the relationship, and a
    provenance record should not acquire referential side effects.

THE BACKFILL INVENTS NOTHING (AC-05)

There is no ``UPDATE`` statement in this revision, and that is the point. The classification
provenance of every pre-existing document is genuinely UNKNOWN: the schema never recorded
whether an administrator typed those values or accepted an endpoint default, and no signal in
the current schema or in ``audit_events`` can distinguish the two (the ``document.registered``
event recorded the resulting level, never the origin of the decision). ``server_default =
'unknown'`` is therefore the whole backfill, and it is a truthful statement rather than a
guess.

Marking existing rows ``'explicit'`` would have been the convenient choice and would have been
a lie of exactly the shape this project has already paid for: a record that asserts a value
was deliberately chosen when nobody knows whether it was. Compare 0005, whose backfill went
the OTHER way for the same reason -- there a real signal existed (``status = 'indexed'`` plus
the historical ``document.indexed`` audit event), so it was used; here none exists, so nothing
is claimed. The direction is not "fill it in optimistically" or "leave it empty", it is
"record precisely what is knowable".

REVERSIBILITY

Fully reversible. ``upgrade()`` only adds columns and ``downgrade()`` only drops them, so no
pre-existing row's data is read, rewritten, or lost in either direction. Round-tripped by
CI's Alembic job against real Postgres (``upgrade head`` -> ``downgrade base`` ->
``upgrade head``); the pytest suite builds its schema with ``Base.metadata.create_all`` on
SQLite and never runs Alembic, so CI is the only thing that checks this file against a real
database. ``op.batch_alter_table`` is used because SQLite cannot attach a NOT NULL column
constraint through a plain ``ALTER TABLE ADD COLUMN`` and cannot ``DROP COLUMN`` at all
without a table rebuild; on Postgres batch mode degrades to plain ALTER statements.

Revision ID: 0006_source_class_defaults
Revises: 0005_document_has_been_indexed
Create Date: 2026-08-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_source_class_defaults"
down_revision: str | None = "0005_document_has_been_indexed"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: The honest provenance of every row that predates this revision. Mirrors
#: app.domain.classification.CLASSIFICATION_UNKNOWN; kept as a literal because a migration
#: must not change meaning when application code is refactored later.
UNKNOWN_PROVENANCE = "unknown"


def upgrade() -> None:
    with op.batch_alter_table("knowledge_sources") as batch_op:
        batch_op.add_column(
            sa.Column(
                "default_access_groups",
                sa.JSON(),
                nullable=False,
                # server_default so existing rows satisfy NOT NULL immediately; new inserts
                # still take their value from the ORM default. '[]' is "not configured".
                server_default=sa.text("'[]'"),
            )
        )

    with op.batch_alter_table("documents") as batch_op:
        batch_op.add_column(
            sa.Column(
                "confidentiality_source",
                sa.String(length=40),
                nullable=False,
                server_default=UNKNOWN_PROVENANCE,
            )
        )
        batch_op.add_column(
            sa.Column(
                "access_groups_source",
                sa.String(length=40),
                nullable=False,
                server_default=UNKNOWN_PROVENANCE,
            )
        )
        batch_op.add_column(
            sa.Column("classification_source_id", sa.String(length=36), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("documents") as batch_op:
        batch_op.drop_column("classification_source_id")
        batch_op.drop_column("access_groups_source")
        batch_op.drop_column("confidentiality_source")

    with op.batch_alter_table("knowledge_sources") as batch_op:
        batch_op.drop_column("default_access_groups")
