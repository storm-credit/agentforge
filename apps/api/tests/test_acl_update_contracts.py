import importlib.util
from collections.abc import Iterator

import pytest

RUNTIME_DEPS = ("fastapi", "pydantic_settings", "sqlalchemy")
pytestmark = pytest.mark.skipif(
    not all(importlib.util.find_spec(p) for p in RUNTIME_DEPS),
    reason="Runtime dependencies are not installed",
)


def test_acl_update_schema_rejects_empty_groups():
    from pydantic import ValidationError

    from app.domain.schemas import DocumentAclUpdate

    with pytest.raises(ValidationError):
        DocumentAclUpdate(access_groups=[], confidentiality_level="internal", reason="x")


def test_acl_update_schema_requires_reason():
    from pydantic import ValidationError

    from app.domain.schemas import DocumentAclUpdate

    with pytest.raises(ValidationError):
        DocumentAclUpdate(
            access_groups=["all-employees"], confidentiality_level="internal", reason=""
        )


def test_acl_update_schema_accepts_valid():
    from app.domain.schemas import DocumentAclUpdate

    payload = DocumentAclUpdate(
        access_groups=["department:HR"], confidentiality_level="restricted", reason="reorg"
    )
    assert payload.access_groups == ["department:HR"]
    assert payload.confidentiality_level == "restricted"


@pytest.fixture
def client():
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
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client_with_db():
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
    with TestClient(app) as test_client:
        yield test_client, testing_session
    Base.metadata.drop_all(bind=engine)


def _indexed_document(client) -> dict:
    source = client.post(
        "/api/v1/knowledge/sources",
        json={"name": "ACL Edit Corpus", "description": "x", "owner_department": "Security"},
    ).json()
    document = client.post(
        "/api/v1/knowledge/documents",
        json={
            "knowledge_source_id": source["id"],
            "title": "Finance Forecast",
            "object_uri": "object://synthetic/finance/forecast.md",
            "checksum": "sha256-forecast",
            "mime_type": "text/markdown",
            "confidentiality_level": "internal",
            "access_groups": ["all-employees"],
        },
    ).json()
    client.post(
        f"/api/v1/knowledge/documents/{document['id']}/index-jobs",
        json={"source_text": "# Finance\n\nQuarterly finance forecast and policy."},
    )
    return document


def _preview_titles(client, source_id, department="Finance"):
    resp = client.post(
        "/api/v1/knowledge/retrieval/preview",
        headers={"X-Agent-Forge-Department": department, "X-Agent-Forge-Clearance": "internal"},
        json={"query": "finance forecast policy", "knowledge_source_ids": [source_id], "top_k": 10},
    )
    return [h["title"] for h in resp.json()["hits"]]


def test_acl_revocation_excludes_document_from_retrieval(client):
    document = _indexed_document(client)
    source_id = document["knowledge_source_id"]

    assert "Finance Forecast" in _preview_titles(client, source_id)

    patch = client.patch(
        f"/api/v1/knowledge/documents/{document['id']}/acl",
        headers={"X-Agent-Forge-User": "acl-admin"},
        json={
            "access_groups": ["department:HR"],
            "confidentiality_level": "internal",
            "reason": "Moved to HR-only after reorg",
        },
    )
    assert patch.status_code == 200
    assert patch.json()["access_groups"] == ["department:HR"]

    assert "Finance Forecast" not in _preview_titles(client, source_id)


def test_acl_change_writes_audit_event(client_with_db):
    from sqlalchemy import select

    from app.domain.models import AuditEvent

    client, testing_session = client_with_db
    document = _indexed_document(client)
    client.patch(
        f"/api/v1/knowledge/documents/{document['id']}/acl",
        headers={"X-Agent-Forge-User": "acl-admin"},
        json={
            "access_groups": ["department:HR"],
            "confidentiality_level": "restricted",
            "reason": "Reclassified restricted",
        },
    )
    with testing_session() as db:
        event = db.scalars(
            select(AuditEvent).where(
                AuditEvent.event_type == "document.acl_changed",
                AuditEvent.target_id == document["id"],
            )
        ).first()
    assert event is not None
    assert event.reason == "Reclassified restricted"
    assert event.payload["before"]["access_groups"] == ["all-employees"]
    assert event.payload["after"]["access_groups"] == ["department:HR"]
    assert event.payload["after"]["confidentiality_level"] == "restricted"


def test_acl_update_rejects_invalid_confidentiality(client):
    document = _indexed_document(client)
    resp = client.patch(
        f"/api/v1/knowledge/documents/{document['id']}/acl",
        json={
            "access_groups": ["all-employees"],
            "confidentiality_level": "top-secret",
            "reason": "x",
        },
    )
    assert resp.status_code == 422


def test_acl_update_rejects_empty_groups(client):
    document = _indexed_document(client)
    resp = client.patch(
        f"/api/v1/knowledge/documents/{document['id']}/acl",
        json={"access_groups": [], "confidentiality_level": "internal", "reason": "x"},
    )
    assert resp.status_code == 422


def test_acl_update_unknown_document_404(client):
    resp = client.patch(
        "/api/v1/knowledge/documents/missing/acl",
        json={
            "access_groups": ["all-employees"],
            "confidentiality_level": "internal",
            "reason": "x",
        },
    )
    assert resp.status_code == 404
