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
    assert run["answer"]  # fallback or LLM answer — non-empty

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
        "citation_validator",
        "guard_output",
    ]
    assert steps[1]["output_summary"]["hit_count"] == 1
    assert steps[1]["output_summary"]["denied_count"] == 1
    assert steps[3]["status"] == "succeeded"
    assert steps[3]["output_summary"]["passed"] is True

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


def test_runtime_run_fails_citation_validation_without_authorized_context(client):
    source = _create_source(client)
    restricted_document = _register_document(
        client,
        source_id=source["id"],
        title="HR Leave Exception Policy",
        object_uri="object://synthetic/hr/leave-exception-required.md",
        checksum="sha256-leave-exception-required-runtime",
        confidentiality_level="restricted",
        access_groups=["department:HR"],
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
            "input": {"message": "restricted leave exceptions"},
        },
    )

    assert run_response.status_code == 201
    run = run_response.json()
    assert run["status"] == "failed"
    assert run["citations"] == []
    assert run["retrieval_denied_count"] == 1
    assert run["guardrail"]["citation_required"] is True
    assert run["guardrail"]["citation_validation_pass"] is False
    assert run["guardrail"]["citation_validation_error_code"] == "NO_CITATION"
    assert run["guardrail"]["security_finalcheck_pass"] is False
    assert run["answer"]  # refusal answer — non-empty

    steps_response = client.get(f"/api/v1/runs/{run['id']}/steps")

    assert steps_response.status_code == 200
    steps = steps_response.json()
    citation_step = steps[3]
    assert citation_step["step_type"] == "citation_validator"
    assert citation_step["status"] == "failed"
    assert citation_step["error_code"] == "NO_CITATION"
    assert citation_step["output_summary"]["passed"] is False

    hits_response = client.get(f"/api/v1/runs/{run['id']}/retrieval-hits")

    assert hits_response.status_code == 200
    assert hits_response.json() == []


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


def _seed_agent_with_indexed_doc(client):
    """Seed a source, agent, published version, and an indexed document. Returns ids dict."""
    source = _create_source(client)
    agent = _create_agent(client)
    version = _create_and_publish_version(client, agent_id=agent["id"], source_id=source["id"])  # noqa: F841
    doc = _register_document(
        client,
        source_id=source["id"],
        title="Holiday Policy",
        object_uri="object://holiday.md",
        checksum="sha256-holiday",
        access_groups=["all-employees"],
    )
    _index_document(
        client,
        document_id=doc["id"],
        source_text="# 휴가\n\n연 5일 유급 휴가가 제공됩니다.",
    )
    return {"agent_id": agent["id"], "source_id": source["id"]}


def test_run_uses_llm_answer_when_gateway_returns(client, monkeypatch):
    from app.services import llm_gateway

    def fake_generate(self, *, question, context, language, temperature=0.2, top_p=None):
        assert len(context) >= 1
        return llm_gateway.GeneratedAnswer(text=f"[{language}] answer", used_llm=True, fallback_used=False)

    monkeypatch.setattr(llm_gateway.LLMGateway, "generate", fake_generate)
    ids = _seed_agent_with_indexed_doc(client)
    resp = client.post(
        "/api/v1/runs",
        json={
            "agent_id": ids["agent_id"],
            "input": {"message": "휴가 며칠?"},
            "knowledge_source_ids": [ids["source_id"]],
            "language": "auto",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["answer"] == "[ko] answer"
    assert len(body["citations"]) >= 1


def test_run_refuses_when_no_authorized_context(client):
    ids = _seed_agent_with_indexed_doc(client)
    resp = client.post(
        "/api/v1/runs",
        headers={"X-Agent-Forge-Groups": "nobody", "X-Agent-Forge-Clearance": "public"},
        json={
            "agent_id": ids["agent_id"],
            "input": {"message": "휴가 며칠?"},
            "knowledge_source_ids": [ids["source_id"]],
            "language": "ko",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["citations"] == []
    assert resp.json()["answer"]
    assert resp.json()["guardrail"]["citation_count"] == 0


def test_run_falls_back_when_llm_unconfigured(client):
    ids = _seed_agent_with_indexed_doc(client)
    resp = client.post(
        "/api/v1/runs",
        json={
            "agent_id": ids["agent_id"],
            "input": {"message": "leave days?"},
            "knowledge_source_ids": [ids["source_id"]],
            "language": "en",
        },
    )
    assert resp.status_code == 201
    run = resp.json()
    assert run["answer"]

    steps_response = client.get(f"/api/v1/runs/{run['id']}/steps")
    assert steps_response.status_code == 200
    steps = steps_response.json()
    generator_step = next(s for s in steps if s["step_type"] == "generator")
    assert generator_step["output_summary"]["mode"] == "fallback"


def test_run_falls_back_to_fake_when_vector_store_errors(client, monkeypatch):
    import app.api.v1.runs as runs_module

    # Set up source + indexed document + published agent (real factory, so indexing works normally)
    source = _create_source(client)
    doc = _register_document(
        client,
        source_id=source["id"],
        title="Remote Work Policy",
        object_uri="object://synthetic/ops/remote-work-fallback.md",
        checksum="sha256-remote-work-fallback",
        access_groups=["all-employees"],
        confidentiality_level="internal",
    )
    _index_document(
        client,
        document_id=doc["id"],
        source_text="# Remote Work\n\nEmployees may request remote work after manager approval.",
    )
    agent = _create_agent(client)
    version = _create_and_publish_version(client, agent_id=agent["id"], source_id=source["id"])

    # Patch the factory AFTER indexing, so only the run's search call gets the broken store
    class _Boom:
        def search(self, **kwargs):
            raise RuntimeError("qdrant down")

    monkeypatch.setattr(runs_module, "get_vector_store", lambda: _Boom())

    resp = client.post(
        "/api/v1/runs",
        headers={
            "X-Agent-Forge-User": "ops-user",
            "X-Agent-Forge-Department": "Operations",
            "X-Agent-Forge-Clearance": "internal",
        },
        json={
            "agent_id": agent["id"],
            "agent_version_id": version["id"],
            "input": {"message": "remote work policy"},
        },
    )
    assert resp.status_code == 201
    run = resp.json()

    steps = client.get(f"/api/v1/runs/{run['id']}/steps").json()
    retriever = next(s for s in steps if s["step_type"] == "retriever")
    assert retriever["output_summary"]["vector_adapter"] == "fake_fallback"
    assert retriever["output_summary"]["degraded"] is True


def test_retrieval_hits_include_chunk_content(client):
    source = _create_source(client)
    doc = _register_document(
        client,
        source_id=source["id"],
        title="Remote Work Policy",
        object_uri="object://synthetic/ops/remote-work-content.md",
        checksum="sha256-remote-work-content",
        access_groups=["all-employees"],
        confidentiality_level="internal",
    )
    _index_document(
        client,
        document_id=doc["id"],
        source_text="remote work is allowed two days per week",
    )
    agent = _create_agent(client)
    version = _create_and_publish_version(client, agent_id=agent["id"], source_id=source["id"])

    run_response = client.post(
        "/api/v1/runs",
        headers={
            "X-Agent-Forge-User": "ops-user",
            "X-Agent-Forge-Department": "Operations",
            "X-Agent-Forge-Clearance": "internal",
        },
        json={
            "agent_id": agent["id"],
            "agent_version_id": version["id"],
            "input": {"message": "remote work policy"},
        },
    )
    assert run_response.status_code == 201
    run = run_response.json()

    hits_response = client.get(f"/api/v1/runs/{run['id']}/retrieval-hits")
    assert hits_response.status_code == 200
    hits = hits_response.json()

    assert hits, "expected at least one retrieval hit"
    assert "content" in hits[0]
    assert any(h.get("content") for h in hits)
