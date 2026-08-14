"""Append-only ingestion lineage: one row per index attempt.

WO-2026-08-14-INGESTION-INSTRUMENTATION-001 (OBS-001, OBS-002). One new table, no new column
on any existing table, and no existing row's data is modified.

WHY A TABLE AND NOT COLUMNS ON ``documents``

A re-index would overwrite the previous attempt. "Which documents did the broken converter
version touch, and what did it produce for them?" is precisely the question last-write-wins
destroys, and it is the question a converter defect forces. Same reasoning as 0005's durable
``has_been_indexed`` flag: the durable record and the volatile current state are different
facts. ``documents.structure_recovered``-style denormalisation was considered and rejected in
the design (docs/10-architecture/ingestion-normalization-design.md section 3-5) for exactly
this reason.

WHAT THE BACKFILL CLAIMS, AND WHAT IT REFUSES TO CLAIM (AC-05)

Two things are genuinely derivable from rows that already exist, so they are derived:

  * ``chunk_count`` -- how many ``document_chunks`` rows the document has.
  * ``structured_chunk_count`` -- how many of those have a non-empty ``section_path``. This is
    the number the Work Order is about, and it is a FACT already sitting in the database: it
    says how many of this document's citations can name a clause instead of "body".

Everything else is marked NOT OBSERVED:

  * ``extraction_status = 'unknown'``. NEVER ``'ok'``. Nothing recorded whether extraction
    succeeded, how much text came out, or whether pages were scanned images. Writing ``'ok'``
    would assert a verified extraction that nobody verified -- the precise failure this Work
    Order exists to expose, reproduced inside the fix.
  * ``index_job_id = NULL``. The attempt that produced the current chunks cannot be identified:
    a re-index without ``force_reindex`` leaves earlier chunk rows in place, so a document's
    chunk set can span several jobs. Attaching them all to the newest job would be a guess
    dressed as lineage.
  * ``converted_mime_type``, ``converter_chain``, ``extracted_char_count``,
    ``source_unit_kind``, ``source_unit_count`` -- NULL. ``converted_mime_type`` in particular
    is RE-DERIVABLE from ``documents.mime_type`` by re-running ``chunker_mime_type_for``, and
    is still left NULL: re-deriving today's code's answer is not a record of what actually ran
    at index time, and a migration that imports application logic silently changes meaning when
    that logic is refactored.
  * ``warnings = []``. No warning is invented for old rows; the same question is answerable
    from ``structured_chunk_count`` (0 with a non-zero ``chunk_count`` is the collapse).

``source_mime_type`` IS filled from ``documents.mime_type``, because that is a stored value
being copied, not a judgement.

Documents with no chunk rows get no row at all. There is no evidence an attempt happened, and
an empty row asserting one would be manufacturing history.

PORTABILITY

The backfill iterates in Python over the Alembic connection rather than using SQL JSON
operators: ``document_chunks.section_path`` is a JSON column, and SQLite (the test/dev path)
stores it as TEXT while Postgres (CI/deploy) parses it. ``_section_path_is_present`` handles
both representations, and ``_backfill_rows`` is a pure function so it is unit-testable without
a database -- the pytest suite builds its schema with ``create_all`` and never runs Alembic,
so a backfill hidden inside ``upgrade()`` would be tested by nothing until CI.

REVERSIBILITY

Fully reversible. ``upgrade()`` creates one table and inserts only into it; ``downgrade()``
drops that table. No pre-existing row is read for modification, rewritten, or lost in either
direction, so a downgrade loses exactly the lineage this revision created and nothing else.
Round-tripped against real Postgres by CI's Alembic job.

Revision ID: 0007_document_ingestions
Revises: 0006_source_class_defaults
Create Date: 2026-08-14
"""

import json
import uuid
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "0007_document_ingestions"
down_revision: str | None = "0006_source_class_defaults"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: The only extraction status a backfilled row may carry. Mirrors
#: app.domain.ingestion_lineage.EXTRACTION_UNKNOWN; kept as a literal because a migration must
#: not change meaning when application code is refactored later.
UNKNOWN_EXTRACTION_STATUS = "unknown"

TABLE_NAME = "document_ingestions"


def _lineage_table() -> sa.Table:
    """A minimal table clause for ``op.bulk_insert`` (column types drive JSON serialisation)."""
    return sa.table(
        TABLE_NAME,
        sa.column("id", sa.String),
        sa.column("document_id", sa.String),
        sa.column("index_job_id", sa.String),
        sa.column("extraction_status", sa.String),
        sa.column("source_mime_type", sa.String),
        sa.column("converted_mime_type", sa.String),
        sa.column("converter_chain", sa.String),
        sa.column("chunk_count", sa.Integer),
        sa.column("structured_chunk_count", sa.Integer),
        sa.column("extracted_char_count", sa.Integer),
        sa.column("source_unit_kind", sa.String),
        sa.column("source_unit_count", sa.Integer),
        sa.column("warnings", sa.JSON),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )


def _section_path_is_present(raw: Any) -> bool:
    """Does this chunk carry a non-empty ``section_path``?

    Postgres hands back a parsed list, SQLite a JSON string, and either may be NULL. Anything
    unparseable counts as ABSENT: this feeds a count of chunks whose citation can name a
    clause, so the cautious direction is to under-claim structure, never to over-claim it.
    """
    value = raw
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return False
    return bool(value)


def _backfill_rows(
    *,
    document_mime_types: dict[str, str],
    chunk_rows: Iterable[tuple[str, Any]],
    created_at: datetime,
) -> list[dict[str, Any]]:
    """Build one lineage row per document that HAS chunks. Pure; see the module docstring."""
    chunk_counts: dict[str, int] = {}
    structured_counts: dict[str, int] = {}
    for document_id, section_path in chunk_rows:
        if document_id not in document_mime_types:
            # A chunk whose document is gone cannot be attributed to a document row.
            continue
        chunk_counts[document_id] = chunk_counts.get(document_id, 0) + 1
        structured_counts.setdefault(document_id, 0)
        if _section_path_is_present(section_path):
            structured_counts[document_id] += 1

    return [
        {
            "id": str(uuid.uuid4()),
            "document_id": document_id,
            "index_job_id": None,
            "extraction_status": UNKNOWN_EXTRACTION_STATUS,
            "source_mime_type": document_mime_types[document_id],
            "converted_mime_type": None,
            "converter_chain": None,
            "chunk_count": chunk_counts[document_id],
            "structured_chunk_count": structured_counts[document_id],
            "extracted_char_count": None,
            "source_unit_kind": None,
            "source_unit_count": None,
            "warnings": [],
            "created_at": created_at,
        }
        for document_id in sorted(chunk_counts)
    ]


def upgrade() -> None:
    op.create_table(
        TABLE_NAME,
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("index_job_id", sa.String(length=36), nullable=True),
        sa.Column("extraction_status", sa.String(length=20), nullable=False),
        sa.Column("source_mime_type", sa.String(length=120), nullable=False),
        sa.Column("converted_mime_type", sa.String(length=120), nullable=True),
        sa.Column("converter_chain", sa.String(length=240), nullable=True),
        # Nullable on purpose: NULL is "not observed", 0 is "observed and it was zero".
        sa.Column("chunk_count", sa.Integer(), nullable=True),
        sa.Column("structured_chunk_count", sa.Integer(), nullable=True),
        sa.Column("extracted_char_count", sa.Integer(), nullable=True),
        sa.Column("source_unit_kind", sa.String(length=20), nullable=True),
        sa.Column("source_unit_count", sa.Integer(), nullable=True),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["index_job_id"], ["index_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_document_ingestions_document_id"), TABLE_NAME, ["document_id"], unique=False
    )
    op.create_index(
        op.f("ix_document_ingestions_index_job_id"), TABLE_NAME, ["index_job_id"], unique=False
    )

    connection = op.get_bind()
    document_mime_types = {
        row[0]: row[1] for row in connection.execute(sa.text("SELECT id, mime_type FROM documents"))
    }
    chunk_rows = [
        (row[0], row[1])
        for row in connection.execute(
            sa.text("SELECT document_id, section_path FROM document_chunks")
        )
    ]
    rows = _backfill_rows(
        document_mime_types=document_mime_types,
        chunk_rows=chunk_rows,
        created_at=datetime.now(UTC),
    )
    if rows:
        op.bulk_insert(_lineage_table(), rows)


def downgrade() -> None:
    op.drop_index(op.f("ix_document_ingestions_index_job_id"), table_name=TABLE_NAME)
    op.drop_index(op.f("ix_document_ingestions_document_id"), table_name=TABLE_NAME)
    op.drop_table(TABLE_NAME)
