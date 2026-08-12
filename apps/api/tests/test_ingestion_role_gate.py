"""Authorization tests for the knowledge-ingestion trust boundary.

WO-2026-08-12-UPLOAD-ROLE-GATE-001: ``POST /knowledge/documents`` (register) and
``POST /knowledge/documents/upload`` (upload + inline index) are the two endpoints that
create a Document, and the upload endpoint additionally creates chunks and vectors in one
request. Both are now gated on ``PRIVILEGED_ROLES`` like every other mutating knowledge
endpoint (archive / restore / ACL patch).

These tests assert more than the status code: AC-01 requires that a denied attempt creates
NOTHING -- no ``documents`` row, no ``index_jobs`` row, no ``document_chunks`` row, no
vector upsert, and no object-store write. A 403 that still wrote a row would pass a
status-only test.

Scope note: this is an authorization change only. It does NOT mitigate prompt injection --
a privileged uploader can still ingest poisoned content, and a document that merely quotes
an injection example contaminates the index exactly as before.
"""

from __future__ import annotations

import importlib.util
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import pytest

RUNTIME_DEPS = ("fastapi", "httpx", "pydantic_settings", "sqlalchemy")


def runtime_deps_available() -> bool:
    return all(importlib.util.find_spec(package) for package in RUNTIME_DEPS)


pytestmark = pytest.mark.skipif(
    not runtime_deps_available(),
    reason="Runtime dependencies are not installed",
)

# Privileged identities. "knowledge-manager" is deliberately used as well as "admin": the
# gate must accept every PRIVILEGED_ROLES member, not just admin.
_ADMIN = {"X-Agent-Forge-User": "ops", "X-Agent-Forge-Roles": "admin"}
_KNOWLEDGE_MANAGER = {
    "X-Agent-Forge-User": "km",
    "X-Agent-Forge-Roles": "knowledge-manager",
}
# Non-privileged but otherwise ordinary employee identity. Note that "developer" is also
# the header-stub DEFAULT (app/core/principal.py), so a caller that sends no role headers
# at all is equally non-privileged.
_EMPLOYEE = {
    "X-Agent-Forge-User": "attacker",
    "X-Agent-Forge-Department": "Engineering",
    "X-Agent-Forge-Roles": "developer",
    "X-Agent-Forge-Groups": "all-employees",
    "X-Agent-Forge-Clearance": "internal",
}


@dataclass
class _Api:
    """TestClient plus a direct session factory, so 'nothing was created' can be asserted
    against the tables themselves rather than through the (ACL-scoped) read API."""

    client: Any
    session_factory: Any

    def counts(self) -> dict[str, int]:
        from sqlalchemy import func, select

        from app.domain.models import Document, DocumentChunk, IndexJob

        with self.session_factory() as session:
            return {
                name: session.scalar(select(func.count()).select_from(model))
                for name, model in (
                    ("documents", Document),
                    ("index_jobs", IndexJob),
                    ("document_chunks", DocumentChunk),
                )
            }

    def audit_events(self, event_type: str) -> list[Any]:
        from sqlalchemy import select

        from app.domain.models import AuditEvent

        with self.session_factory() as session:
            return list(
                session.scalars(
                    select(AuditEvent).where(AuditEvent.event_type == event_type)
                )
            )


@pytest.fixture
def api() -> Iterator[_Api]:
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session, sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.core.database import Base, get_db
    from app.domain import models  # noqa: F401 - register mappings
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

    with TestClient(app) as test_client:
        yield _Api(client=test_client, session_factory=testing_session)

    Base.metadata.drop_all(bind=engine)


def _create_source(api: _Api) -> dict:
    response = api.client.post(
        "/api/v1/knowledge/sources",
        headers=_ADMIN,
        json={
            "name": "Ingestion Gate Corpus",
            "description": "Corpus for the ingestion role-gate tests.",
            "owner_department": "Operations",
        },
    )
    assert response.status_code == 201
    return response.json()


def _document_payload(source_id: str) -> dict:
    return {
        "knowledge_source_id": source_id,
        "title": "Planted Notice",
        "object_uri": "object://synthetic/planted-notice.md",
        "checksum": "sha256-planted-notice",
        "mime_type": "text/markdown",
        # The whole point of the gate: the caller chooses who may read the content.
        "confidentiality_level": "internal",
        "access_groups": ["all-employees"],
    }


class _RecordingStore:
    """Vector store spy that also works if it IS used (so a positive control still
    indexes) while recording every upsert/delete."""

    def __init__(self) -> None:
        from app.domain.vector import FakeVectorStore

        self._inner = FakeVectorStore()
        self.upserted_chunk_ids: list[str] = []
        self.deleted_document_ids: list[str] = []

    def upsert_chunks(self, chunks):
        self.upserted_chunk_ids.extend(chunk.chunk_id for chunk in chunks)
        return self._inner.upsert_chunks(chunks)

    def delete_document(self, document_id: str) -> int:
        self.deleted_document_ids.append(document_id)
        return self._inner.delete_document(document_id)

    def set_document_acl(self, document_id: str, **kwargs):
        return self._inner.set_document_acl(document_id, **kwargs)

    def search(self, **kwargs):
        return self._inner.search(**kwargs)


# --------------------------------------------------------------------------------------
# AC-01: non-privileged principal is denied AND creates nothing
# --------------------------------------------------------------------------------------


def test_register_document_denied_for_non_privileged_and_creates_nothing(api, monkeypatch):
    from app.domain import indexing

    source = _create_source(api)
    before = api.counts()
    assert before == {"documents": 0, "index_jobs": 0, "document_chunks": 0}

    spy = _RecordingStore()
    monkeypatch.setattr(indexing, "get_vector_store", lambda: spy)

    denied = api.client.post(
        "/api/v1/knowledge/documents",
        headers=_EMPLOYEE,
        json=_document_payload(source["id"]),
    )

    assert denied.status_code == 403
    assert denied.json()["detail"] == "Insufficient role for this action"
    # Nothing created: no document row, and therefore no job/chunk/vector downstream.
    assert api.counts() == before
    assert spy.upserted_chunk_ids == []
    # And it is not merely invisible to the denied caller -- an admin cannot see it either.
    assert api.client.get("/api/v1/knowledge/documents", headers=_ADMIN).json() == []


def test_upload_document_denied_for_non_privileged_and_creates_nothing(api, monkeypatch):
    """The upload endpoint is the one that creates document + job + chunks + vectors (and
    optionally an object-store object) in a single request, so all five are asserted."""
    from app.core.config import get_settings
    from app.domain import indexing
    from app.infra.object_store import get_object_store

    # Turn the object store ON so "no original bytes were persisted" is a real assertion
    # rather than vacuously true (the default backend is "none").
    monkeypatch.setenv("AGENT_FORGE_OBJECT_STORE_BACKEND", "memory")
    get_settings.cache_clear()
    get_object_store.cache_clear()
    try:
        source = _create_source(api)
        before = api.counts()
        assert before == {"documents": 0, "index_jobs": 0, "document_chunks": 0}

        spy = _RecordingStore()
        monkeypatch.setattr(indexing, "get_vector_store", lambda: spy)
        object_store = get_object_store()
        assert object_store is not None  # the endpoint resolves this same cached instance

        denied = api.client.post(
            "/api/v1/knowledge/documents/upload",
            headers=_EMPLOYEE,
            data={
                "knowledge_source_id": source["id"],
                "title": "Planted Upload",
                "confidentiality_level": "internal",
                "access_groups": "all-employees",
            },
            files={"file": ("planted.md", b"# Planted\n\nattacker-controlled body.", "text/markdown")},
        )

        assert denied.status_code == 403
        assert denied.json()["detail"] == "Insufficient role for this action"
        assert api.counts() == before
        assert spy.upserted_chunk_ids == []
        assert spy.deleted_document_ids == []
        # No original bytes were persisted either.
        assert object_store._data == {}
        assert api.client.get("/api/v1/knowledge/documents", headers=_ADMIN).json() == []
    finally:
        get_settings.cache_clear()
        get_object_store.cache_clear()


def test_ingestion_denied_for_default_header_stub_principal(api):
    """A caller that sends NO identity headers gets the stub default (roles=developer).
    That default must not be privileged -- otherwise the gate is decorative."""
    source = _create_source(api)

    assert (
        api.client.post(
            "/api/v1/knowledge/documents", json=_document_payload(source["id"])
        ).status_code
        == 403
    )
    assert (
        api.client.post(
            "/api/v1/knowledge/documents/upload",
            data={"knowledge_source_id": source["id"], "title": "Default Stub"},
            files={"file": ("stub.md", b"# Stub\n\nbody.", "text/markdown")},
        ).status_code
        == 403
    )
    assert api.counts() == {"documents": 0, "index_jobs": 0, "document_chunks": 0}


def test_gate_precedes_validation_and_lookup(api):
    """The gate runs BEFORE the knowledge-source lookup and payload validation, so an
    unauthorized caller cannot use the 404/422 responses to probe which knowledge sources
    exist or which confidentiality levels are accepted."""
    for payload in (
        {**_document_payload("does-not-exist"), "confidentiality_level": "internal"},
        {**_document_payload("does-not-exist"), "confidentiality_level": "not-a-level"},
    ):
        response = api.client.post(
            "/api/v1/knowledge/documents", headers=_EMPLOYEE, json=payload
        )
        assert response.status_code == 403

    upload = api.client.post(
        "/api/v1/knowledge/documents/upload",
        headers=_EMPLOYEE,
        data={"knowledge_source_id": "does-not-exist", "title": "Probe"},
        files={"file": ("probe.bin", b"\x00\x01", "application/octet-stream")},
    )
    # Unsupported MIME type would be 415 for a privileged caller; unauthorized loses first.
    assert upload.status_code == 403


# --------------------------------------------------------------------------------------
# AC-03: the denial is audited, naming actor and target
# --------------------------------------------------------------------------------------


def test_denied_register_and_upload_emit_policy_denied_audit_events(api):
    source = _create_source(api)

    api.client.post(
        "/api/v1/knowledge/documents", headers=_EMPLOYEE, json=_document_payload(source["id"])
    )
    api.client.post(
        "/api/v1/knowledge/documents/upload",
        headers=_EMPLOYEE,
        data={"knowledge_source_id": source["id"], "title": "Planted Upload"},
        files={"file": ("planted.md", b"# Planted\n\nbody.", "text/markdown")},
    )

    events = api.audit_events("policy.denied")
    by_action = {event.payload["action"]: event for event in events}
    assert set(by_action) == {"document.register", "document.upload"}

    for action, event in by_action.items():
        # Actor: who attempted it.
        assert event.actor_id == "attacker"
        assert event.actor_department == "Engineering"
        # Target: what they attempted it against.
        assert event.target_type == "knowledge_source"
        assert event.target_id == source["id"]
        # Enough context to reconstruct the decision.
        assert event.payload["principal_roles"] == ["developer"]
        assert "knowledge-manager" in event.reason
        assert action in event.reason


# --------------------------------------------------------------------------------------
# AC-02: privileged principals keep the existing behaviour
# --------------------------------------------------------------------------------------


def test_register_document_allowed_for_privileged_roles(api):
    source = _create_source(api)

    for headers, title in ((_ADMIN, "Admin Doc"), (_KNOWLEDGE_MANAGER, "KM Doc")):
        response = api.client.post(
            "/api/v1/knowledge/documents",
            headers=headers,
            json={**_document_payload(source["id"]), "title": title},
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["title"] == title
        assert body["access_groups"] == ["all-employees"]
        assert body["status"] == "registered"

    assert api.counts()["documents"] == 2


def test_residual_first_time_index_by_non_privileged_reader_is_still_open(api, monkeypatch):
    """OPEN GAP -- this test asserts a limitation, not a desired behaviour.

    Gating register/upload does NOT close every non-privileged path into the active index.
    ``POST /documents/{id}/index-jobs`` requires only READ access to the document while that
    document has never been successfully indexed (``has_been_indexed`` is False), and it
    accepts caller-supplied ``source_text``. So once a knowledge manager registers a
    document (metadata only, the normal two-step flow), any read-authorized employee can
    still be the principal who decides what text lands in the index under that document's
    ACL tag.

    Raising that bar removes the last self-service ingest path and is a product decision of
    the same kind as WO-2026-08-12-UPLOAD-ROLE-GATE-001's, which deliberately scoped it out.
    When a follow-on Work Order closes it, INVERT this test (expect 403 + no chunks) rather
    than deleting it.
    """
    source = _create_source(api)
    registered = api.client.post(
        "/api/v1/knowledge/documents",
        headers=_KNOWLEDGE_MANAGER,
        json=_document_payload(source["id"]),
    )
    assert registered.status_code == 201
    document = registered.json()

    from app.domain import indexing

    spy = _RecordingStore()
    monkeypatch.setattr(indexing, "get_vector_store", lambda: spy)

    job = api.client.post(
        f"/api/v1/knowledge/documents/{document['id']}/index-jobs",
        headers=_EMPLOYEE,
        json={"source_text": "# Notice\n\nemployee-supplied body, never approved."},
    )

    # Reality today: allowed, and it reaches the vector store.
    assert job.status_code == 201, job.text
    assert job.json()["status"] == "succeeded"
    assert spy.upserted_chunk_ids


def test_upload_document_allowed_for_privileged_roles_and_still_indexes(api, monkeypatch):
    from app.domain import indexing

    source = _create_source(api)
    spy = _RecordingStore()
    monkeypatch.setattr(indexing, "get_vector_store", lambda: spy)

    response = api.client.post(
        "/api/v1/knowledge/documents/upload",
        headers=_KNOWLEDGE_MANAGER,
        data={
            "knowledge_source_id": source["id"],
            "title": "Cafeteria Notice",
            "confidentiality_level": "internal",
            "access_groups": "all-employees",
        },
        files={
            "file": (
                "notice.md",
                "# Notice\n\nCafeteria opens at 11:30.".encode("utf-8"),
                "text/markdown",
            )
        },
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["document"]["status"] == "indexed"
    assert payload["index_job"]["status"] == "succeeded"
    assert payload["index_job"]["chunk_count"] >= 1
    assert payload["index_job"]["created_by"] == "km"
    # The full inline pipeline still ran end to end for an authorized caller.
    assert spy.upserted_chunk_ids
    counts = api.counts()
    assert counts["documents"] == 1
    assert counts["index_jobs"] == 1
    assert counts["document_chunks"] >= 1
    assert api.audit_events("policy.denied") == []
