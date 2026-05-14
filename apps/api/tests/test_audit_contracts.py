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


def test_audit_events_can_be_listed_and_filtered(client):
    agent_response = client.post(
        "/api/v1/agents",
        headers={
            "X-Agent-Forge-User": "audit-owner",
            "X-Agent-Forge-Department": "Risk",
        },
        json={
            "name": "Audited Policy Assistant",
            "purpose": "Create audit evidence.",
            "owner_department": "Risk",
        },
    )

    assert agent_response.status_code == 201
    agent = agent_response.json()

    list_response = client.get("/api/v1/audit/events?limit=10")

    assert list_response.status_code == 200
    events = list_response.json()
    assert events[0]["event_type"] == "agent.created"
    assert events[0]["actor_id"] == "audit-owner"
    assert events[0]["actor_department"] == "Risk"
    assert events[0]["target_type"] == "agent"
    assert events[0]["target_id"] == agent["id"]
    assert events[0]["payload"]["name"] == "Audited Policy Assistant"

    filtered_response = client.get("/api/v1/audit/events?event_type=agent.created&q=audit")

    assert filtered_response.status_code == 200
    filtered = filtered_response.json()
    assert [event["id"] for event in filtered] == [events[0]["id"]]


def test_audit_events_support_target_filter(client):
    first_response = client.post(
        "/api/v1/agents",
        json={
            "name": "First Audit Target",
            "purpose": "First target.",
            "owner_department": "Risk",
        },
    )
    second_response = client.post(
        "/api/v1/agents",
        json={
            "name": "Second Audit Target",
            "purpose": "Second target.",
            "owner_department": "Risk",
        },
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    first_agent = first_response.json()

    response = client.get(
        f"/api/v1/audit/events?target_type=agent&target_id={first_agent['id']}"
    )

    assert response.status_code == 200
    events = response.json()
    assert len(events) == 1
    assert events[0]["target_id"] == first_agent["id"]
