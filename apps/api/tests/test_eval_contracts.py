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
        test_client.testing_session = testing_session
        yield test_client

    Base.metadata.drop_all(bind=engine)


def test_eval_run_report_can_be_persisted_and_read_as_overview(client):
    create_response = client.post(
        "/api/v1/eval/runs",
        headers={"X-Agent-Forge-User": "eval-api-runner"},
        json=_report_payload(),
    )

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["corpus_id"] == "synthetic-corpus-v0.1"
    assert created["mode"] == "api"
    assert created["status"] == "passed"
    assert created["passed"] is True
    assert created["total_cases"] == 2
    assert created["passed_cases"] == 2
    assert created["failed_cases"] == 0
    assert created["suite_counts"] == {"acl": 1, "rag-core": 1}
    assert created["created_by"] == "eval-api-runner"
    assert created["summary"]["pass_rate"] == 1
    assert created["summary"]["citation_coverage"] == 1
    assert created["summary"]["trace_completeness"] == 1
    assert created["model_routing_policy_ref"] == (
        "packages/shared-contracts/model-routing-policy.v0.1.json"
    )
    assert created["budget_class"] == "release-gate"
    assert created["model_route_summary"]["answer_generator"]["tier"] == "standard-rag"
    assert created["summary"]["model_route_summary"]["critic"]["escalation_tier"] == "deep-review"
    assert len(created["results"]) == 2

    overview_response = client.get("/api/v1/eval/overview")

    assert overview_response.status_code == 200
    overview = overview_response.json()
    assert overview["run"]["id"] == created["id"]
    assert overview["run"]["status"] == "passed"
    assert overview["suite_counts"] == {"acl": 1, "rag-core": 1}
    assert [result["case_id"] for result in overview["results"]] == ["acl_001", "rag_001"]

    latest_response = client.get("/api/v1/eval/runs/latest")

    assert latest_response.status_code == 200
    assert latest_response.json()["id"] == created["id"]

    results_response = client.get(f"/api/v1/eval/runs/{created['id']}/results")

    assert results_response.status_code == 200
    results = results_response.json()
    assert results[0]["case_id"] == "acl_001"
    assert results[1]["citation_document_ids"] == ["HR-001"]

    list_response = client.get("/api/v1/eval/runs?limit=1")

    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [created["id"]]


def test_eval_run_baseline_approval_is_audited(client):
    create_response = client.post(
        "/api/v1/eval/runs",
        headers={"X-Agent-Forge-User": "eval-api-runner"},
        json=_report_payload(),
    )
    created = create_response.json()

    approve_response = client.post(
        f"/api/v1/eval/runs/{created['id']}/approve-baseline",
        headers={"X-Agent-Forge-User": "qa-lead"},
        json={"reason": "Synthetic corpus v0.1 release gate passed"},
    )

    assert approve_response.status_code == 200
    approved = approve_response.json()
    assert approved["approved_baseline_by"] == "qa-lead"
    assert approved["approved_baseline_at"] is not None

    from sqlalchemy import select

    from app.domain.models import AuditEvent

    with client.testing_session() as db:
        events = list(db.scalars(select(AuditEvent).order_by(AuditEvent.created_at)))

    baseline_events = [
        event for event in events if event.event_type == "eval_run.baseline_approved"
    ]
    assert len(baseline_events) == 1
    assert baseline_events[0].target_id == created["id"]
    assert baseline_events[0].actor_id == "qa-lead"


def test_eval_run_rejects_incomplete_model_route_summary(client):
    payload = _report_payload()
    payload["model_route_summary"].pop("critic")

    response = client.post(
        "/api/v1/eval/runs",
        headers={"X-Agent-Forge-User": "eval-api-runner"},
        json=payload,
    )

    assert response.status_code == 422
    assert "missing runtime stages" in response.json()["detail"]


def _report_payload() -> dict:
    from app.domain.model_routing import runtime_model_route_summary

    return {
        "corpus_id": "synthetic-corpus-v0.1",
        "mode": "api",
        "model_routing_policy_ref": "packages/shared-contracts/model-routing-policy.v0.1.json",
        "budget_class": "release-gate",
        "model_route_summary": runtime_model_route_summary(),
        "passed": True,
        "total_cases": 2,
        "passed_cases": 2,
        "failed_cases": 0,
        "suite_counts": {"acl": 1, "rag-core": 1},
        "setup_findings": [],
        "setup": {
            "run_token": "20260513-150000-contract",
            "knowledge_source_id": "source-1",
            "agent_id": "agent-1",
            "agent_version_id": "version-1",
        },
        "results": [
            {
                "case_id": "rag_001",
                "suite": "rag-core",
                "expected_behavior": "answer",
                "passed": True,
                "findings": [],
                "run_id": "11111111-1111-1111-1111-111111111111",
                "status": "succeeded",
                "citation_document_ids": ["HR-001"],
                "retrieval_document_ids": ["HR-001"],
                "retrieval_denied_count": 0,
            },
            {
                "case_id": "acl_001",
                "suite": "acl",
                "expected_behavior": "policy_denied",
                "passed": True,
                "findings": [],
                "run_id": "22222222-2222-2222-2222-222222222222",
                "status": "failed",
                "citation_document_ids": [],
                "retrieval_document_ids": [],
                "retrieval_denied_count": 1,
            },
        ],
    }
