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


def test_agent_and_version_contract(client):
    agent_response = client.post(
        "/api/v1/agents",
        headers={
            "X-Agent-Forge-User": "agent-owner",
            "X-Agent-Forge-Department": "Operations",
        },
        json={
            "name": "Policy Assistant",
            "purpose": "Answer internal policy questions with citations.",
            "owner_department": "Operations",
        },
    )

    assert agent_response.status_code == 201
    agent = agent_response.json()
    assert agent["id"]
    assert agent["name"] == "Policy Assistant"
    assert agent["status"] == "draft"

    detail_response = client.get(f"/api/v1/agents/{agent['id']}")

    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == agent["id"]

    update_response = client.patch(
        f"/api/v1/agents/{agent['id']}",
        headers={"X-Agent-Forge-User": "agent-owner"},
        json={"purpose": "Answer internal policy questions with traceable citations."},
    )

    assert update_response.status_code == 200
    assert update_response.json()["purpose"] == (
        "Answer internal policy questions with traceable citations."
    )

    version_response = client.post(
        "/api/v1/agents/versions",
        headers={"X-Agent-Forge-User": "agent-owner"},
        json={
            "agent_id": agent["id"],
            "version": 1,
            "config": {
                "citation_required": True,
                "knowledge_source_ids": [],
            },
        },
    )

    assert version_response.status_code == 201
    version = version_response.json()
    assert version["agent_id"] == agent["id"]
    assert version["version"] == 1
    assert version["created_by"] == "agent-owner"

    versions_response = client.get(f"/api/v1/agents/{agent['id']}/versions")

    assert versions_response.status_code == 200
    assert [item["id"] for item in versions_response.json()] == [version["id"]]

    validate_response = client.post(
        f"/api/v1/agents/versions/{version['id']}/validate",
        headers={"X-Agent-Forge-User": "agent-owner"},
        json={"reason": "Contract test validation"},
    )

    assert validate_response.status_code == 200
    assert validate_response.json()["status"] == "validated"

    publish_response = client.post(
        f"/api/v1/agents/versions/{version['id']}/publish",
        headers={"X-Agent-Forge-User": "platform-admin"},
        json={"reason": "Contract test publish"},
    )

    assert publish_response.status_code == 200
    assert publish_response.json()["status"] == "published"

    list_response = client.get("/api/v1/agents")

    assert list_response.status_code == 200
    listed_agents = list_response.json()
    assert [item["id"] for item in listed_agents] == [agent["id"]]
    assert listed_agents[0]["status"] == "published"


def test_knowledge_source_and_document_contract(client):
    source_response = client.post(
        "/api/v1/knowledge/sources",
        headers={
            "X-Agent-Forge-User": "knowledge-manager",
            "X-Agent-Forge-Department": "Operations",
        },
        json={
            "name": "Pilot Policies",
            "description": "Synthetic policy documents for Sprint 0.",
            "owner_department": "Operations",
            "default_confidentiality_level": "internal",
        },
    )

    assert source_response.status_code == 201
    source = source_response.json()
    assert source["id"]
    assert source["default_confidentiality_level"] == "internal"

    document_response = client.post(
        "/api/v1/knowledge/documents",
        headers={"X-Agent-Forge-User": "knowledge-manager"},
        json={
            "knowledge_source_id": source["id"],
            "title": "Remote Work Policy",
            "object_uri": "object://synthetic/hr/remote-work.md",
            "checksum": "sha256-synthetic-remote-work",
            "mime_type": "text/markdown",
            "confidentiality_level": "internal",
            "access_groups": ["all-employees"],
            "status": "registered",
            "effective_date": "2026-05-09",
        },
    )

    assert document_response.status_code == 201
    document = document_response.json()
    assert document["knowledge_source_id"] == source["id"]
    assert document["access_groups"] == ["all-employees"]

    list_response = client.get("/api/v1/knowledge/documents")

    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [document["id"]]


def test_document_registration_rejects_unknown_source(client):
    response = client.post(
        "/api/v1/knowledge/documents",
        json={
            "knowledge_source_id": "missing-source",
            "title": "Unknown Source Document",
            "object_uri": "object://synthetic/missing.md",
            "checksum": "sha256-missing",
            "mime_type": "text/markdown",
            "confidentiality_level": "internal",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Knowledge source not found"
