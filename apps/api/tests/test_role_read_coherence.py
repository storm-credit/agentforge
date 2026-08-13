"""Read-visibility vs mutation-rights coherence (WO-2026-08-13-ROLE-READ-COHERENCE-001).

AgentForge had two unreconciled authorization mechanisms: ``enforce_roles(PRIVILEGED_ROLES)``
gates mutations for ``{admin, platform-admin, knowledge-manager}``, while a separate literal
``"admin" in principal.roles`` gated the read-side see-everything bypasses. The result was
capabilities that could not be exercised -- a knowledge-manager may restore an archived
document but could not list archived documents to find its id, and may publish an agent
version but got 404 enumerating the versions of an unpublished agent.

These tests exercise the WORKFLOW, not the mutation call. A test that only asserts
``POST /documents/{id}/restore`` returns 200 for a knowledge-manager passes both before and
after the fix and proves nothing: the defect was in the discovery step that precedes it.

The negative half matters just as much. Only DISCOVERY-of-a-granted-mutation was reconciled;
the general ACL bypass (see every document regardless of authorization) is still literally
``admin``. The AC-03 tests below pin that: a knowledge-manager's visible document set is
unchanged except for archived rows its own ACL already permits.
"""

from __future__ import annotations

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


# --------------------------------------------------------------------------------------
# Identities. Every principal below carries the SAME ACL inputs (all-employees group,
# internal clearance) so that any difference in what they can see is attributable to the
# ROLE alone, which is what this Work Order is about.
# --------------------------------------------------------------------------------------
_ACL_INPUTS = {
    "X-Agent-Forge-Department": "Operations",
    "X-Agent-Forge-Groups": "all-employees",
    "X-Agent-Forge-Clearance": "internal",
}


def _identity(user: str, roles: str) -> dict[str, str]:
    return {"X-Agent-Forge-User": user, "X-Agent-Forge-Roles": roles, **_ACL_INPUTS}


_ADMIN = _identity("ops-admin", "admin")
_PLATFORM_ADMIN = _identity("ops-platform", "platform-admin")
_KNOWLEDGE_MANAGER = _identity("km", "knowledge-manager")
_SECURITY_AUDITOR = _identity("auditor", "security-auditor")
_DEVELOPER = _identity("dev", "developer")

# The two roles this Work Order is about: privileged for mutations, previously excluded
# from every read-side bypass.
_RECONCILED_ROLES = {
    "platform-admin": _PLATFORM_ADMIN,
    "knowledge-manager": _KNOWLEDGE_MANAGER,
}
# Roles that must be entirely unaffected: they hold no PRIVILEGED_ROLES membership.
_UNPRIVILEGED_ROLES = {
    "security-auditor": _SECURITY_AUDITOR,
    "developer": _DEVELOPER,
}


@pytest.fixture
def client():
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
        yield test_client

    Base.metadata.drop_all(bind=engine)


# --------------------------------------------------------------------------------------
# Corpus helpers
# --------------------------------------------------------------------------------------


def _create_source(client) -> str:
    response = client.post(
        "/api/v1/knowledge/sources",
        headers=_ADMIN,
        json={
            "name": "Role Coherence Corpus",
            "description": "Fixture corpus for the role read-coherence tests.",
            "owner_department": "Operations",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _register(
    client,
    source_id: str,
    title: str,
    *,
    confidentiality_level: str = "internal",
    access_groups: tuple[str, ...] = ("all-employees",),
    headers: dict[str, str] | None = None,
) -> dict:
    response = client.post(
        "/api/v1/knowledge/documents",
        headers=headers or _KNOWLEDGE_MANAGER,
        json={
            "knowledge_source_id": source_id,
            "title": title,
            "object_uri": f"object://synthetic/{title.lower().replace(' ', '-')}.md",
            "checksum": f"sha256-{title.lower().replace(' ', '-')}",
            "mime_type": "text/markdown",
            "confidentiality_level": confidentiality_level,
            "access_groups": list(access_groups),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _ids(client, headers: dict[str, str], *, include_archived: bool = False) -> set[str]:
    params = {"include_archived": "true"} if include_archived else None
    response = client.get("/api/v1/knowledge/documents", headers=headers, params=params)
    assert response.status_code == 200
    return {d["id"] for d in response.json()}


# ======================================================================================
# AC-02 -- a granted capability is exercisable end to end
# ======================================================================================


def test_knowledge_manager_completes_archive_then_restore_workflow(client):
    """The whole point of the Work Order: the FULL workflow, discovery step included.

    Every call below is made as ``knowledge-manager`` -- never as admin -- so nothing here
    silently rides on admin's ACL bypass. Step 3 (discovery) is the step that used to be
    impossible; steps 1, 2 and 4 already worked and would pass a status-only test.
    """
    source_id = _create_source(client)
    document = _register(client, source_id, "Quarterly Ops Handbook")
    document_id = document["id"]

    # 1. archive (mutation the role already held)
    archived = client.delete(
        f"/api/v1/knowledge/documents/{document_id}", headers=_KNOWLEDGE_MANAGER
    )
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"

    # 2. it drops out of the default listing -- the operator has now "lost" the document
    assert document_id not in _ids(client, _KNOWLEDGE_MANAGER)

    # 3. DISCOVERY: find the archived id again without being admin. This is what used to
    #    return a list with the flag silently ignored, making step 4 unreachable in practice.
    discovered = client.get(
        "/api/v1/knowledge/documents",
        headers=_KNOWLEDGE_MANAGER,
        params={"include_archived": "true"},
    )
    assert discovered.status_code == 200
    discovered_row = next(
        (d for d in discovered.json() if d["id"] == document_id), None
    )
    assert discovered_row is not None, "knowledge-manager cannot discover the id it may restore"
    assert discovered_row["status"] == "archived"

    # 3b. Discovery is METADATA only -- it does not unlock the archived document's content.
    #     Chunk listing still runs principal_can_access_document, which fails closed on the
    #     archived lifecycle status for every non-admin.
    chunks = client.get(
        f"/api/v1/knowledge/documents/{document_id}/chunks", headers=_KNOWLEDGE_MANAGER
    )
    assert chunks.status_code == 403

    # 4. restore, using the id obtained in step 3
    restored = client.post(
        f"/api/v1/knowledge/documents/{discovered_row['id']}/restore",
        headers=_KNOWLEDGE_MANAGER,
        params={"reason": "archived by mistake"},
    )
    assert restored.status_code == 200
    assert restored.json()["status"] == "registered"

    # 5. the document is back in the ordinary listing, workflow closed
    assert document_id in _ids(client, _KNOWLEDGE_MANAGER)


def test_platform_admin_completes_archive_then_restore_workflow(client):
    """Same workflow for the other role that holds restore but held no read bypass."""
    source_id = _create_source(client)
    document_id = _register(client, source_id, "Platform Runbook")["id"]

    assert (
        client.delete(
            f"/api/v1/knowledge/documents/{document_id}", headers=_PLATFORM_ADMIN
        ).status_code
        == 200
    )
    assert document_id not in _ids(client, _PLATFORM_ADMIN)
    assert document_id in _ids(client, _PLATFORM_ADMIN, include_archived=True)
    assert (
        client.post(
            f"/api/v1/knowledge/documents/{document_id}/restore", headers=_PLATFORM_ADMIN
        ).status_code
        == 200
    )
    assert document_id in _ids(client, _PLATFORM_ADMIN)


def test_knowledge_manager_lists_versions_of_an_unpublished_agent_it_may_publish(client):
    """A role that may publish a version must be able to enumerate the versions.

    Again the full workflow: create the agent, create a draft version, ENUMERATE it, then
    validate and publish the id that enumeration returned.
    """
    agent = client.post(
        "/api/v1/agents",
        headers=_KNOWLEDGE_MANAGER,
        json={"name": "Ops Assistant", "purpose": "p", "owner_department": "Operations"},
    ).json()
    assert agent["status"] == "draft"

    created = client.post(
        "/api/v1/agents/versions",
        headers=_KNOWLEDGE_MANAGER,
        json={"agent_id": agent["id"], "config": {"citation_required": True}},
    )
    assert created.status_code == 201

    # The agent is unpublished. This used to be 404 for knowledge-manager.
    listed = client.get(f"/api/v1/agents/{agent['id']}/versions", headers=_KNOWLEDGE_MANAGER)
    assert listed.status_code == 200
    version_ids = [v["id"] for v in listed.json()]
    assert version_ids == [created.json()["id"]]

    # The agent itself is discoverable too, both by id and in the list -- otherwise the
    # caller could never reach the versions endpoint above in the first place.
    assert (
        client.get(f"/api/v1/agents/{agent['id']}", headers=_KNOWLEDGE_MANAGER).status_code == 200
    )
    listed_agents = client.get("/api/v1/agents", headers=_KNOWLEDGE_MANAGER)
    assert listed_agents.status_code == 200
    assert agent["id"] in {a["id"] for a in listed_agents.json()}

    # ... and the enumerated id is actually actionable end to end.
    assert (
        client.post(
            f"/api/v1/agents/versions/{version_ids[0]}/validate",
            headers=_KNOWLEDGE_MANAGER,
            json={"reason": "coherence test"},
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/v1/agents/versions/{version_ids[0]}/publish",
            headers=_KNOWLEDGE_MANAGER,
            json={"reason": "coherence test"},
        ).status_code
        == 200
    )


# ======================================================================================
# AC-03 -- nothing widened: the general ACL bypass stays exactly where it was
# ======================================================================================


@pytest.mark.parametrize("role_name", sorted(_RECONCILED_ROLES))
def test_reconciled_roles_cannot_discover_archived_documents_outside_their_acl(
    client, role_name
):
    """Discovery is ACL-BOUND. Relaxing the lifecycle-status gate must not relax the ACL.

    Two independent negative controls, each isolating one ACL dimension:
      * group intersection  -- internal classification the caller's clearance clears, but an
        access group the caller is not in;
      * clearance rank      -- a group the caller IS in, but a classification above its
        clearance.
    Both documents are archived, and the caller asks for archived rows explicitly.
    """
    headers = _RECONCILED_ROLES[role_name]
    source_id = _create_source(client)

    mine = _register(client, source_id, "Own Team Notes")
    other_group = _register(
        client, source_id, "HR Disciplinary File", access_groups=("hr-restricted",)
    )
    above_clearance = _register(
        client, source_id, "Restricted Board Pack", confidentiality_level="restricted"
    )

    for document in (mine, other_group, above_clearance):
        assert (
            client.delete(
                f"/api/v1/knowledge/documents/{document['id']}", headers=_ADMIN
            ).status_code
            == 200
        )

    visible = _ids(client, headers, include_archived=True)
    assert mine["id"] in visible, "in-ACL archived row should be discoverable"
    assert other_group["id"] not in visible, "group ACL bypassed by archived discovery"
    assert above_clearance["id"] not in visible, "clearance ACL bypassed by archived discovery"

    # Control: admin's general bypass is unchanged and still sees all three.
    admin_visible = _ids(client, _ADMIN, include_archived=True)
    assert {mine["id"], other_group["id"], above_clearance["id"]} <= admin_visible


@pytest.mark.parametrize("role_name", sorted(_RECONCILED_ROLES))
def test_reconciled_roles_gain_nothing_in_the_non_archived_listing(client, role_name):
    """The before/after set comparison for live (non-archived) documents.

    Nothing about the ordinary listing changed for these roles: they see exactly the
    documents their ACL permits, identical to what an unprivileged principal with the same
    ACL inputs sees. Only ``admin`` reads past the ACL.
    """
    headers = _RECONCILED_ROLES[role_name]
    source_id = _create_source(client)

    mine = _register(client, source_id, "Team Handbook")
    other_group = _register(
        client, source_id, "HR Case Notes", access_groups=("hr-restricted",)
    )
    above_clearance = _register(
        client, source_id, "Board Pack", confidentiality_level="restricted"
    )

    # Same ACL inputs, no privileged role at all -> the reference set.
    reference = _ids(client, _DEVELOPER)
    assert _ids(client, headers) == reference == {mine["id"]}

    # ... and asking for archived rows does not smuggle live out-of-ACL rows in either.
    assert _ids(client, headers, include_archived=True) == reference

    assert {other_group["id"], above_clearance["id"]} <= _ids(client, _ADMIN)


@pytest.mark.parametrize("role_name", sorted(_UNPRIVILEGED_ROLES))
def test_unprivileged_roles_still_cannot_discover_archived_documents(client, role_name):
    """security-auditor holds AUDIT_READ_ROLES but no mutation right, so it gets no
    discovery: the reconciliation keys on the restore capability, not on "seniority"."""
    headers = _UNPRIVILEGED_ROLES[role_name]
    source_id = _create_source(client)
    document_id = _register(client, source_id, "Ops Notice")["id"]
    assert (
        client.delete(
            f"/api/v1/knowledge/documents/{document_id}", headers=_ADMIN
        ).status_code
        == 200
    )

    # The flag stays silently ignored (200, not 403) for these callers.
    assert document_id not in _ids(client, headers, include_archived=True)
    # ... and restore is refused, so no capability is left unexercisable.
    assert (
        client.post(
            f"/api/v1/knowledge/documents/{document_id}/restore", headers=headers
        ).status_code
        == 403
    )


def test_agent_build_state_was_already_readable_through_mutations(client):
    """Executable evidence for the justification in ``agents._is_builder``.

    The claim in that docstring -- that widening the agent reads to PRIVILEGED_ROLES is not
    a read-privilege increase, because both roles could already obtain the same data through
    mutations they hold -- would be an assertion-by-reading otherwise. It is pinned here so
    that if these mutation paths ever start checking publication status, the justification
    fails loudly instead of silently rotting.
    """
    agent = client.post(
        "/api/v1/agents",
        headers=_KNOWLEDGE_MANAGER,
        json={"name": "Unpublished", "purpose": "secret purpose", "owner_department": "Ops"},
    ).json()
    version = client.post(
        "/api/v1/agents/versions",
        headers=_KNOWLEDGE_MANAGER,
        json={"agent_id": agent["id"], "config": {"system_prompt": "unreleased"}},
    ).json()

    # PATCH with an empty body: no publication-status check, returns the draft record.
    patched = client.patch(
        f"/api/v1/agents/{agent['id']}", headers=_KNOWLEDGE_MANAGER, json={}
    )
    assert patched.status_code == 200
    assert patched.json()["purpose"] == "secret purpose"
    assert patched.json()["status"] == "draft"

    # validate: no publication-status check either, returns the full draft config.
    validated = client.post(
        f"/api/v1/agents/versions/{version['id']}/validate",
        headers=_KNOWLEDGE_MANAGER,
        json={"reason": "read path"},
    )
    assert validated.status_code == 200
    assert validated.json()["config"] == {"system_prompt": "unreleased"}


@pytest.mark.parametrize("role_name", sorted(_UNPRIVILEGED_ROLES))
def test_unprivileged_roles_still_cannot_see_unpublished_agents(client, role_name):
    headers = _UNPRIVILEGED_ROLES[role_name]
    agent = client.post(
        "/api/v1/agents",
        headers=_KNOWLEDGE_MANAGER,
        json={"name": "Draft Only", "purpose": "p", "owner_department": "Operations"},
    ).json()
    client.post(
        "/api/v1/agents/versions",
        headers=_KNOWLEDGE_MANAGER,
        json={"agent_id": agent["id"], "config": {"citation_required": True}},
    )

    assert client.get(f"/api/v1/agents/{agent['id']}", headers=headers).status_code == 404
    assert (
        client.get(f"/api/v1/agents/{agent['id']}/versions", headers=headers).status_code == 404
    )
    assert agent["id"] not in {
        a["id"] for a in client.get("/api/v1/agents", headers=headers).json()
    }


def test_unprivileged_reader_never_sees_draft_versions_of_a_published_agent(client):
    """Regression guard on the second thing the versions endpoint gates: even when the
    agent IS published, draft/validated configs stay hidden from non-builders."""
    agent = client.post(
        "/api/v1/agents",
        headers=_KNOWLEDGE_MANAGER,
        json={"name": "Published Agent", "purpose": "p", "owner_department": "Operations"},
    ).json()
    first = client.post(
        "/api/v1/agents/versions",
        headers=_KNOWLEDGE_MANAGER,
        json={"agent_id": agent["id"], "config": {"citation_required": True}},
    ).json()
    client.post(
        f"/api/v1/agents/versions/{first['id']}/publish",
        headers=_KNOWLEDGE_MANAGER,
        json={"reason": "publish"},
    )
    draft = client.post(
        "/api/v1/agents/versions",
        headers=_KNOWLEDGE_MANAGER,
        json={"agent_id": agent["id"], "config": {"secret_prompt": "unreleased"}},
    ).json()

    developer_versions = client.get(
        f"/api/v1/agents/{agent['id']}/versions", headers=_DEVELOPER
    )
    assert developer_versions.status_code == 200
    assert {v["id"] for v in developer_versions.json()} == {first["id"]}
    assert draft["id"] not in {v["id"] for v in developer_versions.json()}


def test_run_read_scope_is_untouched_by_this_work_order(client):
    """runs.py's literal admin check is a GENERAL bypass, not discovery for a granted
    mutation: no PRIVILEGED_ROLES member holds any mutation over another user's run. It was
    classified and deliberately left alone, so pin that it did not drift."""
    agent = client.post(
        "/api/v1/agents",
        headers=_KNOWLEDGE_MANAGER,
        json={"name": "Runner", "purpose": "p", "owner_department": "Operations"},
    ).json()
    version = client.post(
        "/api/v1/agents/versions",
        headers=_KNOWLEDGE_MANAGER,
        json={"agent_id": agent["id"], "config": {"citation_required": True}},
    ).json()
    client.post(
        f"/api/v1/agents/versions/{version['id']}/publish",
        headers=_KNOWLEDGE_MANAGER,
        json={"reason": "publish"},
    )

    run = client.post(
        "/api/v1/runs",
        headers=_DEVELOPER,
        json={"agent_id": agent["id"], "input": {"message": "hello"}},
    )
    assert run.status_code == 201
    run_id = run.json()["id"]

    for headers in (_KNOWLEDGE_MANAGER, _PLATFORM_ADMIN, _SECURITY_AUDITOR):
        assert client.get(f"/api/v1/runs/{run_id}", headers=headers).status_code == 403
        assert run_id not in {r["id"] for r in client.get("/api/v1/runs", headers=headers).json()}

    assert client.get(f"/api/v1/runs/{run_id}", headers=_ADMIN).status_code == 200
