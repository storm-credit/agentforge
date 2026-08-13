"""Authorization tests for ``POST /knowledge/sources`` (create_source).

WO-2026-08-13-MUTATION-GATE-SWEEP-001, AC-03. ``create_source`` had NO ``enforce_roles``
call at all, so any principal -- including the header-stub default ``developer`` identity,
i.e. a caller that sends no identity headers whatsoever -- could create a knowledge source
and choose its ``default_confidentiality_level``. It is now gated on ``PRIVILEGED_ROLES``
like every sibling knowledge mutation (register / upload / archive / restore / ACL patch).

Following ``test_ingestion_role_gate.py``: these tests assert more than the status code. A
403 that still wrote a row would pass a status-only test, so "nothing was created" is
asserted against the table itself rather than through the (clearance-scoped) read API.
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

_ADMIN = {"X-Agent-Forge-User": "ops", "X-Agent-Forge-Roles": "admin"}
# Every PRIVILEGED_ROLES member must be accepted, not just admin.
_KNOWLEDGE_MANAGER = {"X-Agent-Forge-User": "km", "X-Agent-Forge-Roles": "knowledge-manager"}
# Holds audit-read rights but NOT mutation rights: the gate must be the mutation set, not
# "any named role".
_SECURITY_AUDITOR = {"X-Agent-Forge-User": "sec", "X-Agent-Forge-Roles": "security-auditor"}
_EMPLOYEE = {
    "X-Agent-Forge-User": "attacker",
    "X-Agent-Forge-Department": "Engineering",
    "X-Agent-Forge-Roles": "developer",
    "X-Agent-Forge-Groups": "all-employees",
    "X-Agent-Forge-Clearance": "internal",
}

_PAYLOAD = {
    "name": "Planted Source",
    "description": "Created by a non-privileged principal.",
    "owner_department": "Engineering",
    # The point of the gate: the caller chooses the classification label the source is
    # listed under.
    "default_confidentiality_level": "restricted",
}


@dataclass
class _Api:
    client: Any
    session_factory: Any

    def source_count(self) -> int:
        from sqlalchemy import func, select

        from app.domain.models import KnowledgeSource

        with self.session_factory() as session:
            return session.scalar(select(func.count()).select_from(KnowledgeSource))

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


def test_create_source_denied_for_non_privileged_and_creates_nothing(api):
    assert api.source_count() == 0

    denied = api.client.post("/api/v1/knowledge/sources", headers=_EMPLOYEE, json=_PAYLOAD)

    assert denied.status_code == 403
    assert denied.json()["detail"] == "Insufficient role for this action"
    # Nothing was created -- the assertion the status code alone would not make.
    assert api.source_count() == 0
    # And it is not merely invisible to the denied caller: an admin sees no source either.
    assert api.client.get("/api/v1/knowledge/sources", headers=_ADMIN).json() == []
    # No success event was written.
    assert api.audit_events("knowledge_source.created") == []


def test_create_source_denied_for_default_header_stub_principal(api):
    """No identity headers at all -> roles=("developer",) server-side. Still denied."""
    denied = api.client.post("/api/v1/knowledge/sources", json=_PAYLOAD)

    assert denied.status_code == 403
    assert api.source_count() == 0


def test_create_source_denied_for_audit_read_only_role(api):
    """security-auditor holds AUDIT_READ_ROLES but no mutation rights."""
    denied = api.client.post(
        "/api/v1/knowledge/sources", headers=_SECURITY_AUDITOR, json=_PAYLOAD
    )

    assert denied.status_code == 403
    assert api.source_count() == 0


def test_create_source_denial_is_audited(api):
    denied = api.client.post("/api/v1/knowledge/sources", headers=_EMPLOYEE, json=_PAYLOAD)
    assert denied.status_code == 403

    events = api.audit_events("policy.denied")
    assert len(events) == 1
    event = events[0]
    assert event.actor_id == "attacker"
    assert event.target_type == "knowledge_source"
    assert event.payload["action"] == "knowledge_source.create"
    assert event.payload["principal_roles"] == ["developer"]


def test_create_source_authorizes_before_validating_the_body(api):
    """AUTHORIZE FIRST: an unauthorized caller must not be able to distinguish a rejected
    classification label (422) from a rejected identity (403), and must not learn that its
    body would otherwise have been accepted."""
    denied = api.client.post(
        "/api/v1/knowledge/sources",
        headers=_EMPLOYEE,
        json={**_PAYLOAD, "default_confidentiality_level": "not-a-real-level"},
    )

    assert denied.status_code == 403
    assert api.source_count() == 0
    # Positive control for the ordering claim: the SAME body from a privileged caller is the
    # one that reaches validation and gets 422.
    rejected = api.client.post(
        "/api/v1/knowledge/sources",
        headers=_ADMIN,
        json={**_PAYLOAD, "default_confidentiality_level": "not-a-real-level"},
    )
    assert rejected.status_code == 422
    assert api.source_count() == 0


@pytest.mark.parametrize("headers", [_ADMIN, _KNOWLEDGE_MANAGER])
def test_create_source_allowed_for_every_privileged_role(api, headers):
    """Positive control: the gate is the mutation role set, and the endpoint still works."""
    created = api.client.post("/api/v1/knowledge/sources", headers=headers, json=_PAYLOAD)

    assert created.status_code == 201
    body = created.json()
    assert body["default_confidentiality_level"] == "restricted"
    assert api.source_count() == 1

    events = api.audit_events("knowledge_source.created")
    assert len(events) == 1
    assert events[0].target_id == body["id"]
    assert api.audit_events("policy.denied") == []
