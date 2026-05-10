import hashlib
import importlib.util
from collections.abc import Iterator
from types import SimpleNamespace

import pytest


RUNTIME_DEPS = ("fastapi", "httpx", "pydantic_settings", "sqlalchemy")


def runtime_deps_available() -> bool:
    return all(importlib.util.find_spec(package) for package in RUNTIME_DEPS)


pytestmark = pytest.mark.skipif(
    not runtime_deps_available(),
    reason="Runtime dependencies are not installed",
)


@pytest.fixture
def api_context(tmp_path):
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session, sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.core.database import Base, get_db
    from app.domain import models  # noqa: F401
    from app.infra.storage import LocalObjectStorage, get_object_storage_provider
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

    object_storage_path = tmp_path / "object-storage"

    def override_storage_provider():
        return lambda: LocalObjectStorage(base_path=object_storage_path, bucket="test-documents")

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_object_storage_provider] = override_storage_provider

    with TestClient(app) as test_client:
        yield SimpleNamespace(
            client=test_client,
            sessionmaker=testing_session,
            object_storage_path=object_storage_path,
        )

    Base.metadata.drop_all(bind=engine)


def test_upload_stores_raw_file_creates_metadata_and_audit_event(api_context):
    client = api_context.client
    source = _create_source(client)
    content = b"# Remote Work\n\nEmployees may request remote work after manager approval.\n"

    upload_response = client.post(
        "/api/v1/knowledge/documents/upload",
        params={
            "knowledge_source_id": source["id"],
            "title": "Remote Work Policy",
            "access_groups": "all-employees,department:Operations",
            "effective_date": "2026-05-10",
        },
        headers={
            "Content-Type": "text/markdown",
            "X-Agent-Forge-Filename": "../Remote Work.md",
            "X-Agent-Forge-User": "knowledge-manager",
            "X-Agent-Forge-Department": "Operations",
        },
        content=content,
    )

    assert upload_response.status_code == 201
    document = upload_response.json()
    assert document["title"] == "Remote Work Policy"
    assert document["mime_type"] == "text/markdown"
    assert document["checksum"] == "sha256-" + hashlib.sha256(content).hexdigest()
    assert document["object_uri"].startswith("object://test-documents/knowledge/")
    assert document["object_uri"].endswith("/Remote-Work.md")
    assert document["access_groups"] == ["all-employees", "department:Operations"]

    stored_path = (
        api_context.object_storage_path
        / "test-documents"
        / "knowledge"
        / source["id"]
        / "documents"
        / document["id"]
        / "Remote-Work.md"
    )
    assert stored_path.read_bytes() == content

    from sqlalchemy import select

    from app.domain.models import AuditEvent

    with api_context.sessionmaker() as db:
        events = list(db.scalars(select(AuditEvent).order_by(AuditEvent.created_at)))

    upload_events = [event for event in events if event.event_type == "document.uploaded"]
    assert len(upload_events) == 1
    assert upload_events[0].target_id == document["id"]
    assert upload_events[0].actor_id == "knowledge-manager"
    assert upload_events[0].payload["checksum"] == document["checksum"]
    assert upload_events[0].payload["size_bytes"] == len(content)


def test_index_job_reads_uploaded_markdown_from_storage_when_source_text_absent(api_context):
    client = api_context.client
    source = _create_source(client)
    content = (
        b"# Remote Work\n\n"
        b"Company-wide remote work rules.\n\n"
        b"## Eligibility\n\n"
        b"Employees may request remote work after manager approval."
    )
    document = _upload_document(client, source_id=source["id"], content=content)

    job_response = client.post(
        f"/api/v1/knowledge/documents/{document['id']}/index-jobs",
        headers={"X-Agent-Forge-User": "storage-indexer"},
        json={"chunking": {"strategy": "line-heading", "chunk_size": 900, "chunk_overlap": 0}},
    )

    assert job_response.status_code == 201
    job = job_response.json()
    assert job["status"] == "succeeded"
    assert job["stage"] == "upsert"
    assert job["chunk_count"] == 2
    assert job["config"]["source"] == "object_store"
    assert job["created_by"] == "storage-indexer"

    chunks_response = client.get(f"/api/v1/knowledge/documents/{document['id']}/chunks")

    assert chunks_response.status_code == 200
    chunks = chunks_response.json()
    assert len(chunks) == 2
    assert chunks[1]["section_path"] == ["Remote Work", "Eligibility"]
    assert chunks[1]["citation_locator"] == (
        "Uploaded Remote Work / Remote Work > Eligibility / lines 7-7"
    )


def _create_source(client) -> dict:
    response = client.post(
        "/api/v1/knowledge/sources",
        json={
            "name": "Upload Corpus",
            "description": "Documents uploaded through object storage.",
            "owner_department": "Operations",
        },
    )
    assert response.status_code == 201
    return response.json()


def _upload_document(client, *, source_id: str, content: bytes) -> dict:
    response = client.post(
        "/api/v1/knowledge/documents/upload",
        params={
            "knowledge_source_id": source_id,
            "title": "Uploaded Remote Work",
            "access_groups": "all-employees",
            "effective_date": "2026-05-10",
        },
        headers={
            "Content-Type": "text/markdown",
            "X-Agent-Forge-Filename": "remote-work.md",
        },
        content=content,
    )
    assert response.status_code == 201
    return response.json()
