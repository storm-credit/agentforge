"""The documents LIST carries each document's most recent ingestion lineage.

WO-2026-08-14-LINEAGE-VISIBILITY-002 (AC-01, AC-02, AC-06).

WHY THIS FILE EXISTS SEPARATELY FROM test_ingestion_lineage.py

That file proves the lineage is RECORDED. This one proves it is REACHABLE from the only
route a knowledge console actually calls when it is listing documents. Between the two there
was a gap: ``IndexJobRead`` carried the record, but only from three job-scoped routes that
need a ``job_id`` the caller does not have when it is rendering a list, and there is no
``GET /documents/{id}`` and no index-job list route. WO-...-LINEAGE-VISIBILITY-001 was
scoped to the frontend alone and could not be implemented for exactly that reason.

WHAT IS DELIBERATELY NOT ASSERTED HERE

Nothing about ACL scoping is CHANGED by this Work Order, so the scoping contract stays where
it already lives (test_metadata_contracts.py, test_role_read_coherence.py,
test_clearance_fail_closed.py -- all untouched). The one ACL assertion below is narrower and
specific to the new field: lineage must ride the SAME filtered list, so a document a
principal cannot see contributes no lineage either. That is a leak test for the new payload,
not a restatement of the scoping rules.
"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest

_ADMIN = {
    "X-Agent-Forge-User": "admin",
    "X-Agent-Forge-Roles": "admin",
    "X-Agent-Forge-Department": "Operations",
}
_EMPLOYEE = {
    "X-Agent-Forge-User": "emp",
    "X-Agent-Forge-Roles": "employee",
    "X-Agent-Forge-Department": "Finance",
    "X-Agent-Forge-Groups": "finance-team",
    "X-Agent-Forge-Clearance": "internal",
}

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@pytest.fixture
def api():
    """A hermetic app whose ENGINE the test can observe, so query counts are measurable."""
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session, sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.core.database import Base, get_db
    from app.domain import models  # noqa: F401
    from app.main import create_app

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db() -> Iterator[Session]:
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        client.engine = engine
        client.session_factory = testing_session
        yield client
        client.app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


# ---------------------------------------------------------------------------------------
# Fixture builders -- rows are written straight through the ORM so each test controls the
# exact lineage shape (including ``created_at`` ordering and the backfill's 'unknown'
# status, which live code never writes).
# ---------------------------------------------------------------------------------------
def _source(api, name: str = "Policies") -> str:
    from app.domain.models import KnowledgeSource

    with api.session_factory() as session:
        source = KnowledgeSource(name=name, owner_department="Operations")
        session.add(source)
        session.commit()
        return source.id


def _document(
    api,
    source_id: str,
    *,
    title: str,
    mime_type: str = "text/markdown",
    access_groups: list[str] | None = None,
    confidentiality_level: str = "internal",
) -> str:
    from app.domain.models import Document

    with api.session_factory() as session:
        document = Document(
            knowledge_source_id=source_id,
            title=title,
            object_uri=f"object://{title}",
            checksum=f"sha256-{title}",
            mime_type=mime_type,
            confidentiality_level=confidentiality_level,
            access_groups=["all-employees"] if access_groups is None else access_groups,
            status="indexed",
        )
        session.add(document)
        session.commit()
        return document.id


def _ingestion(api, document_id: str, *, created_at: datetime, **fields) -> str:
    from app.domain.models import DocumentIngestion

    payload = {
        "extraction_status": "ok",
        "source_mime_type": "text/markdown",
        "converted_mime_type": "text/markdown",
        "converter_chain": "inline/1>text/markdown",
        "chunk_count": 3,
        "structured_chunk_count": 3,
        "extracted_char_count": 120,
        "warnings": [],
    }
    payload.update(fields)
    with api.session_factory() as session:
        row = DocumentIngestion(document_id=document_id, created_at=created_at, **payload)
        session.add(row)
        session.commit()
        return row.id


def _listed(api, headers=_ADMIN, **params) -> list[dict]:
    response = api.get("/api/v1/knowledge/documents", headers=headers, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def _by_title(api, headers=_ADMIN, **params) -> dict[str, dict]:
    return {d["title"]: d for d in _listed(api, headers=headers, **params)}


T0 = datetime(2026, 8, 14, 9, 0, tzinfo=UTC)


# =======================================================================================
# AC-01: one, several, and no ingestion rows
# =======================================================================================
class TestTheListCarriesTheLatestIngestion:
    def test_a_document_with_one_ingestion_row_carries_it(self, api):
        source = _source(api)
        document_id = _document(api, source, title="Structured")
        _ingestion(api, document_id, created_at=T0)

        (listed,) = _listed(api)
        assert listed["id"] == document_id
        ingestion = listed["ingestion"]
        assert ingestion is not None
        assert ingestion["document_id"] == document_id
        assert ingestion["extraction_status"] == "ok"
        assert ingestion["chunk_count"] == 3
        assert ingestion["structured_chunk_count"] == 3
        assert ingestion["converted_mime_type"] == "text/markdown"
        assert ingestion["warnings"] == []

    def test_several_rows_resolve_to_the_most_recent_attempt(self, api):
        """Append-only means a re-indexed document has a HISTORY. The list is a current-state
        view, so it must show the newest attempt -- and showing the oldest would be worse than
        showing nothing, because a since-repaired document would keep reporting a collapse."""
        source = _source(api)
        document_id = _document(api, source, title="Reindexed", mime_type=DOCX_MIME)
        _ingestion(
            api,
            document_id,
            created_at=T0,
            source_mime_type=DOCX_MIME,
            converted_mime_type="text/plain",
            converter_chain="python-docx/1.2.0>text/plain",
            chunk_count=1,
            structured_chunk_count=0,
            warnings=["HEADING_DETECTION_UNAVAILABLE", "NO_HEADINGS_DETECTED"],
        )
        _ingestion(api, document_id, created_at=T0 + timedelta(minutes=5), chunk_count=7)
        newest_id = _ingestion(
            api, document_id, created_at=T0 + timedelta(hours=2), chunk_count=9
        )

        (listed,) = _listed(api)
        assert listed["ingestion"]["id"] == newest_id
        assert listed["ingestion"]["chunk_count"] == 9
        assert listed["ingestion"]["warnings"] == []

    def test_a_document_with_no_ingestion_rows_reports_null(self, api):
        """NOT an omitted key and NOT an empty object: a registered-but-never-indexed document
        has to be distinguishable from an observed attempt, and the field is the only place
        that distinction can be made."""
        source = _source(api)
        _document(api, source, title="Never indexed")

        (listed,) = _listed(api)
        assert "ingestion" in listed
        assert listed["ingestion"] is None

    def test_a_backfilled_row_is_carried_through_as_unknown_not_as_ok(self, api):
        """0007's backfill writes extraction_status='unknown' WITH real chunk counts, because
        the counts are derivable from existing rows and the conversion quality is not. The read
        model must not launder that into a success: a consumer that only looked at
        structured_chunk_count would call this document healthy, so the status has to survive
        the trip verbatim."""
        source = _source(api)
        document_id = _document(api, source, title="Pre-instrumentation")
        _ingestion(
            api,
            document_id,
            created_at=T0,
            extraction_status="unknown",
            converted_mime_type=None,
            converter_chain=None,
            chunk_count=3,
            structured_chunk_count=2,
            extracted_char_count=None,
            warnings=[],
        )

        (listed,) = _listed(api)
        ingestion = listed["ingestion"]
        assert ingestion["extraction_status"] == "unknown"
        assert ingestion["converted_mime_type"] is None
        assert ingestion["converter_chain"] is None
        # Counts the backfill DID derive are still counts; only the unobserved fields are null.
        assert ingestion["chunk_count"] == 3
        assert ingestion["structured_chunk_count"] == 2
        assert ingestion["extracted_char_count"] is None

    def test_null_counts_stay_null_and_are_never_rendered_as_zero(self, api):
        source = _source(api)
        document_id = _document(api, source, title="Failed attempt")
        _ingestion(
            api,
            document_id,
            created_at=T0,
            extraction_status="failed",
            converted_mime_type=None,
            converter_chain=None,
            chunk_count=None,
            structured_chunk_count=None,
            extracted_char_count=None,
            warnings=[],
        )

        (listed,) = _listed(api)
        ingestion = listed["ingestion"]
        assert ingestion["extraction_status"] == "failed"
        assert ingestion["chunk_count"] is None
        assert ingestion["structured_chunk_count"] is None

    def test_documents_with_and_without_lineage_coexist_in_one_page(self, api):
        source = _source(api)
        with_lineage = _document(api, source, title="With")
        _ingestion(api, with_lineage, created_at=T0)
        _document(api, source, title="Without")

        rows = _by_title(api)
        assert rows["With"]["ingestion"] is not None
        assert rows["Without"]["ingestion"] is None


# =======================================================================================
# AC-02: no query per document
# =======================================================================================
class TestListingDoesNotIssueAQueryPerDocument:
    """The eager load in ``list_documents`` is the whole point of this class.

    A naive ``document.ingestion`` access lazy-loads, which is one extra SELECT per row --
    invisible in a test that only checks the payload, and linear in corpus size in production.
    The assertion is deliberately about GROWTH rather than an absolute number, so it does not
    break when an unrelated query is added or removed elsewhere in the request.
    """

    def _add_documents_then_count_selects(self, api, *, add: int) -> tuple[int, int]:
        """Add ``add`` documents (each with lineage) and return (SELECTs, rows listed)."""
        from sqlalchemy import event

        source = _source(api, name=f"Source-{add}")
        for index in range(add):
            document_id = _document(api, source, title=f"Doc-{add}-{index}")
            _ingestion(api, document_id, created_at=T0 + timedelta(seconds=index))

        statements: list[str] = []

        def record(conn, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith("SELECT"):
                statements.append(statement)

        event.listen(api.engine, "before_cursor_execute", record)
        try:
            listed = _listed(api)
        finally:
            event.remove(api.engine, "before_cursor_execute", record)

        assert all(row["ingestion"] is not None for row in listed)
        return len(statements), len(listed)

    def test_query_count_does_not_grow_with_the_number_of_documents(self, api):
        one_selects, one_rows = self._add_documents_then_count_selects(api, add=1)
        many_selects, many_rows = self._add_documents_then_count_selects(api, add=11)
        # Same database, so the second listing returns the first document too -- 1 then 12.
        assert (one_rows, many_rows) == (1, 12)
        assert one_selects == many_selects, (
            f"listing {one_rows} document took {one_selects} SELECTs and listing {many_rows} "
            f"took {many_selects}; the ingestion relationship is being lazy-loaded per row (N+1)"
        )

    def test_the_ingestion_relationship_is_eager_loaded_in_one_extra_query(self, api):
        """Pins the mechanism, not just the symptom: exactly ONE additional SELECT covers the
        whole page (``WHERE document_id IN (...)``)."""
        from sqlalchemy import event

        source = _source(api)
        for index in range(5):
            document_id = _document(api, source, title=f"Doc-{index}")
            _ingestion(api, document_id, created_at=T0 + timedelta(seconds=index))

        statements: list[str] = []

        def record(conn, cursor, statement, parameters, context, executemany):
            statements.append(" ".join(statement.split()))

        event.listen(api.engine, "before_cursor_execute", record)
        try:
            _listed(api)
        finally:
            event.remove(api.engine, "before_cursor_execute", record)

        ingestion_queries = [s for s in statements if "document_ingestions" in s]
        assert len(ingestion_queries) == 1, ingestion_queries


# =======================================================================================
# AC-06: the new field rides the EXISTING ACL filter -- it does not open a side channel
# =======================================================================================
def test_lineage_is_absent_for_documents_the_principal_cannot_see(api):
    """Not a restatement of the scoping rules (those tests are untouched): this asserts the
    new payload cannot leak metadata about a document the existing filter already removed."""
    source = _source(api)
    visible = _document(api, source, title="Finance visible", access_groups=["finance-team"])
    hidden = _document(api, source, title="HR only", access_groups=["hr-team"])
    _ingestion(api, visible, created_at=T0)
    _ingestion(api, hidden, created_at=T0, chunk_count=99)

    titles = _by_title(api, headers=_EMPLOYEE)
    assert set(titles) == {"Finance visible"}
    assert titles["Finance visible"]["ingestion"]["chunk_count"] == 3

    admin_titles = _by_title(api, headers=_ADMIN)
    assert admin_titles["HR only"]["ingestion"]["chunk_count"] == 99


def test_pagination_still_windows_the_acl_filtered_list_with_lineage_attached(api):
    source = _source(api)
    for index in range(4):
        document_id = _document(api, source, title=f"Page-{index}")
        _ingestion(api, document_id, created_at=T0 + timedelta(seconds=index))

    page = _listed(api, limit=2, offset=0)
    assert len(page) == 2
    assert all(row["ingestion"] is not None for row in page)
