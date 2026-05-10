import importlib.util
from collections.abc import Iterator

import pytest


RUNTIME_DEPS = ("fastapi", "httpx", "pydantic_settings", "sqlalchemy")


def runtime_deps_available() -> bool:
    return all(importlib.util.find_spec(package) for package in RUNTIME_DEPS)


pytestmark = pytest.mark.skipif(
    not runtime_deps_available(),
    reason="Runtime dependencies are not installed",
)


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


def test_runtime_run_records_steps_hits_and_acl_trace(client):
    source = _create_source(client)
    public_document = _register_document(
        client,
        source_id=source["id"],
        title="Remote Work Policy",
        object_uri="object://synthetic/ops/remote-work.md",
        checksum="sha256-remote-work-runtime",
        access_groups=["all-employees"],
    )
    restricted_document = _register_document(
        client,
        source_id=source["id"],
        title="HR Leave Exception Policy",
        object_uri="object://synthetic/hr/leave-exception.md",
        checksum="sha256-leave-exception-runtime",
        confidentiality_level="restricted",
        access_groups=["department:HR"],
    )
    _index_document(
        client,
        document_id=public_document["id"],
        source_text=(
            "# Remote Work\n\n"
            "Employees may request remote work after manager approval."
        ),
    )
    _index_document(
        client,
        document_id=restricted_document["id"],
        source_text="# Leave Exceptions\n\nHR may approve restricted leave exceptions.",
    )
    agent = _create_agent(client)
    version = _create_and_publish_version(client, agent_id=agent["id"], source_id=source["id"])

    run_response = client.post(
        "/api/v1/runs",
        headers={
            "X-Agent-Forge-User": "finance-user",
            "X-Agent-Forge-Department": "Finance",
            "X-Agent-Forge-Clearance": "internal",
        },
        json={
            "agent_id": agent["id"],
            "agent_version_id": version["id"],
            "input": {"message": "remote work manager approval"},
        },
    )

    assert run_response.status_code == 201
    run = run_response.json()
    assert run["status"] == "succeeded"
    assert run["agent_version_id"] == version["id"]
    assert run["retrieval_denied_count"] == 1
    assert run["guardrail"]["acl_filter_applied"] is True
    assert run["guardrail"]["citation_count"] == 1
    assert run["citations"][0]["document_id"] == public_document["id"]
    assert run["citations"][0]["chunk_id"]
    assert run["answer"] == "Synthetic runtime response based on 1 authorized citation(s)."

    detail_response = client.get(f"/api/v1/runs/{run['id']}")

    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == run["id"]

    steps_response = client.get(f"/api/v1/runs/{run['id']}/steps")

    assert steps_response.status_code == 200
    steps = steps_response.json()
    assert [step["step_type"] for step in steps] == [
        "guard_input",
        "retriever",
        "generator",
        "guard_output",
    ]
    assert steps[1]["output_summary"]["hit_count"] == 1
    assert steps[1]["output_summary"]["denied_count"] == 1

    hits_response = client.get(f"/api/v1/runs/{run['id']}/retrieval-hits")

    assert hits_response.status_code == 200
    hits = hits_response.json()
    assert len(hits) == 1
    assert hits[0]["document_id"] == public_document["id"]
    assert hits[0]["used_in_context"] is True
    assert hits[0]["used_as_citation"] is True
    assert "department:Finance" in hits[0]["acl_filter_snapshot"]["subjects"]
    assert restricted_document["id"] not in [hit["document_id"] for hit in hits]


def test_runtime_run_requires_published_version(client):
    agent = _create_agent(client)
    version_response = client.post(
        "/api/v1/agents/versions",
        json={
            "agent_id": agent["id"],
            "version": 1,
            "config": {"citation_required": True},
        },
    )
    version = version_response.json()

    run_response = client.post(
        "/api/v1/runs",
        json={
            "agent_id": agent["id"],
            "agent_version_id": version["id"],
            "input": {"message": "Can I run this draft version?"},
        },
    )

    assert run_response.status_code == 400
    assert run_response.json()["detail"] == "Agent version is not published"


def _create_source(client) -> dict:
    response = client.post(
        "/api/v1/knowledge/sources",
        json={
            "name": "Runtime Corpus",
            "description": "Synthetic runtime corpus.",
            "owner_department": "Operations",
        },
    )
    assert response.status_code == 201
    return response.json()


def _register_document(
    client,
    *,
    source_id: str,
    title: str,
    object_uri: str,
    checksum: str,
    access_groups: list[str],
    confidentiality_level: str = "internal",
) -> dict:
    response = client.post(
        "/api/v1/knowledge/documents",
        json={
            "knowledge_source_id": source_id,
            "title": title,
            "object_uri": object_uri,
            "checksum": checksum,
            "mime_type": "text/markdown",
            "confidentiality_level": confidentiality_level,
            "access_groups": access_groups,
            "effective_date": "2026-05-10",
        },
    )
    assert response.status_code == 201
    return response.json()


def _index_document(client, *, document_id: str, source_text: str) -> dict:
    response = client.post(
        f"/api/v1/knowledge/documents/{document_id}/index-jobs",
        headers={"X-Agent-Forge-User": "runtime-indexer"},
        json={"source_text": source_text},
    )
    assert response.status_code == 201
    job = response.json()
    assert job["status"] == "succeeded"
    return job


def _create_agent(client) -> dict:
    response = client.post(
        "/api/v1/agents",
        json={
            "name": "Runtime Policy Assistant",
            "purpose": "Answer policy questions with traceable citations.",
            "owner_department": "Operations",
        },
    )
    assert response.status_code == 201
    return response.json()


def _create_and_publish_version(client, *, agent_id: str, source_id: str) -> dict:
    version_response = client.post(
        "/api/v1/agents/versions",
        json={
            "agent_id": agent_id,
            "version": 1,
            "config": {
                "citation_required": True,
                "knowledge_source_ids": [source_id],
            },
        },
    )
    assert version_response.status_code == 201
    version = version_response.json()

    publish_response = client.post(
        f"/api/v1/agents/versions/{version['id']}/publish",
        json={"reason": "Runtime contract test publish"},
    )
    assert publish_response.status_code == 200
    return publish_response.json()
