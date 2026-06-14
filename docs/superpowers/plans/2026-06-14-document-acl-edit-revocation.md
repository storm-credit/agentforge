# Document ACL Editing + Revocation Propagation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `PATCH /api/v1/knowledge/documents/{id}/acl` endpoint that changes a document's `access_groups`/`confidentiality_level`, propagates the change to the Qdrant chunk payload so retrieval reflects it immediately, and audits every change with a `reason`.

**Architecture:** ACL is enforced as an in-query Qdrant payload filter, so revocation must update the chunk payload (`access_groups`, `confidentiality_rank`) — not just Postgres. A new `set_document_acl` vector-store method does this via `set_payload` (no re-embedding). The endpoint updates Postgres (`Document`, `DocumentChunk.acl_snapshot`), syncs Qdrant, and writes a `document.acl_changed` audit event; any sync failure rolls back (fail-closed).

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic v2, qdrant-client, pytest.

**Environment:** Python = `apps/api/.venv/Scripts/python.exe`. Run pytest with `apps/api/.env` moved aside (baseline 81). uvicorn has no `--reload`.

---

### Task 1: `set_document_acl` on the vector store (protocol + Fake + Qdrant)

**Files:**
- Modify: `apps/api/app/domain/vector.py` (add to `VectorStore` Protocol + `FakeVectorStore`)
- Modify: `apps/api/app/infra/qdrant_store.py` (add to `QdrantVectorStore`)
- Test: `apps/api/tests/test_qdrant_store_contracts.py`

- [ ] **Step 1: Write the failing test** — append to `apps/api/tests/test_qdrant_store_contracts.py`:

```python
def test_set_document_acl_updates_payload_and_revokes_access():
    store = _store()
    _upsert(store, chunk_id="d:1", document_id="d", content="finance policy",
            title="Finance", groups=("all-employees",), rank=1)

    # visible before revocation
    before = store.search(
        query=VectorQuery(query_text="finance policy", top_k=10),
        documents=[],
        acl_filter=build_acl_filter(_principal()),
    )
    assert [h.document_id for h in before.hits] == ["d"]

    # revoke: replace groups with one the principal is not in
    updated = store.set_document_acl(
        "d", access_groups=("department:HR",), confidentiality_rank=1
    )
    assert updated == 1

    after = store.search(
        query=VectorQuery(query_text="finance policy", top_k=10),
        documents=[],
        acl_filter=build_acl_filter(_principal()),
    )
    assert after.hits == ()


def test_set_document_acl_missing_collection_returns_zero():
    client = QdrantClient(":memory:")
    store = QdrantVectorStore(client=client, embed=_stub_embed, dim=4, collection="chunks_active")
    assert store.set_document_acl("nope", access_groups=("x",), confidentiality_rank=1) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests/test_qdrant_store_contracts.py::test_set_document_acl_updates_payload_and_revokes_access -v`
Expected: FAIL with `AttributeError: 'QdrantVectorStore' object has no attribute 'set_document_acl'`

- [ ] **Step 3: Add to the `VectorStore` Protocol** in `apps/api/app/domain/vector.py` (after the `delete_document` signature, ~line 88):

```python
    def set_document_acl(
        self, document_id: str, *, access_groups: tuple[str, ...], confidentiality_rank: int
    ) -> int:
        ...
```

- [ ] **Step 4: Implement on `FakeVectorStore`** in `apps/api/app/domain/vector.py`. Add an `_acl_updates` dict in `__init__` and the method:

```python
    def __init__(self) -> None:
        self._deleted_document_ids: set[str] = set()
        self._acl_updates: dict[str, tuple[tuple[str, ...], int]] = {}

    def set_document_acl(
        self, document_id: str, *, access_groups: tuple[str, ...], confidentiality_rank: int
    ) -> int:
        # The fake reads the live Document for search, so this only records the
        # call so callers/tests can assert it fired. Returns affected chunk count
        # is unknown to the fake, so report 0 (the live Postgres state is authoritative).
        self._acl_updates[document_id] = (tuple(access_groups), confidentiality_rank)
        return 0
```

- [ ] **Step 5: Implement on `QdrantVectorStore`** in `apps/api/app/infra/qdrant_store.py` (after `delete_document`):

```python
    def set_document_acl(
        self, document_id: str, *, access_groups: tuple[str, ...], confidentiality_rank: int
    ) -> int:
        if not self._client.collection_exists(self._collection):
            return 0
        selector = qm.Filter(
            must=[
                qm.FieldCondition(
                    key="document_id", match=qm.MatchValue(value=document_id)
                )
            ]
        )
        affected = self._client.count(
            collection_name=self._collection,
            count_filter=selector,
            exact=True,
        ).count
        if affected == 0:
            return 0
        self._client.set_payload(
            collection_name=self._collection,
            payload={
                "access_groups": list(access_groups),
                "confidentiality_rank": confidentiality_rank,
            },
            points_selector=qm.FilterSelector(filter=selector),
        )
        return affected
```

- [ ] **Step 6: Run both new tests to verify they pass**

Run: `apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests/test_qdrant_store_contracts.py -v -k set_document_acl`
Expected: 2 passed

- [ ] **Step 7: Commit**

```bash
git add apps/api/app/domain/vector.py apps/api/app/infra/qdrant_store.py apps/api/tests/test_qdrant_store_contracts.py
git commit -m "feat(vector): set_document_acl payload sync for ACL revocation"
```

---

### Task 2: `DocumentAclUpdate` schema

**Files:**
- Modify: `apps/api/app/domain/schemas.py` (add after `DocumentRead`, ~line 104)
- Test: `apps/api/tests/test_acl_update_contracts.py` (new — schema validation portion)

- [ ] **Step 1: Write the failing test** — create `apps/api/tests/test_acl_update_contracts.py` with the schema validation tests (the full endpoint tests are added in Task 3; start with the schema):

```python
import importlib.util

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests/test_acl_update_contracts.py -v`
Expected: FAIL with `ImportError: cannot import name 'DocumentAclUpdate'`

- [ ] **Step 3: Add the schema** in `apps/api/app/domain/schemas.py` after `DocumentRead` (~line 104):

```python
class DocumentAclUpdate(BaseModel):
    access_groups: list[str] = Field(min_length=1)
    confidentiality_level: str = Field(min_length=1, max_length=40)
    reason: str = Field(min_length=1, max_length=500)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests/test_acl_update_contracts.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/domain/schemas.py apps/api/tests/test_acl_update_contracts.py
git commit -m "feat(schema): DocumentAclUpdate (set semantics, required reason)"
```

---

### Task 3: `PATCH /documents/{id}/acl` endpoint

**Files:**
- Modify: `apps/api/app/api/v1/knowledge.py` (add endpoint + import `DocumentAclUpdate`, `get_vector_store`, `confidentiality_rank`)
- Test: `apps/api/tests/test_acl_update_contracts.py` (append endpoint tests)

Note: invalid `confidentiality_level` is validated in the endpoint against `CONFIDENTIALITY_RANK` (the schema only checks non-empty), returning 422.

- [ ] **Step 1: Write the failing tests** — append to `apps/api/tests/test_acl_update_contracts.py`. Reuse the `client` fixture pattern from `test_metadata_contracts.py` (copy it into this file):

```python
from collections.abc import Iterator


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


def test_acl_change_writes_audit_event(client):
    from app.domain.models import AuditEvent
    from sqlalchemy import select

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
    # inspect via a fresh session through the same in-memory engine override
    db = client.app.dependency_overrides  # marker; real assertion via API below
    events = client.get(f"/api/v1/audit/events?target_id={document['id']}")
    # if no audit GET exists, assert through the returned document instead:
    assert events.status_code in (200, 404)


def test_acl_update_rejects_invalid_confidentiality(client):
    document = _indexed_document(client)
    resp = client.patch(
        f"/api/v1/knowledge/documents/{document['id']}/acl",
        json={"access_groups": ["all-employees"], "confidentiality_level": "top-secret", "reason": "x"},
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
        json={"access_groups": ["all-employees"], "confidentiality_level": "internal", "reason": "x"},
    )
    assert resp.status_code == 404
```

Note: the audit assertion above is intentionally loose because there is no audit GET endpoint. Replace `test_acl_change_writes_audit_event` with a direct DB check using a module-level engine. Simpler: assert the audit event by querying the DB through a shared engine. To keep it robust, rewrite that test to build its own engine/session (see Step 1b).

- [ ] **Step 1b: Replace the audit test with a direct-DB version** that shares one engine across the app and the assertion. Restructure the fixture to expose the sessionmaker:

```python
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
```

Delete the loose `test_acl_change_writes_audit_event` from Step 1 (keep only this version).

- [ ] **Step 2: Run tests to verify they fail**

Run: `apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests/test_acl_update_contracts.py -v`
Expected: endpoint tests FAIL with 404/405 (route not registered)

- [ ] **Step 3: Add imports** to `apps/api/app/api/v1/knowledge.py`. Extend the `app.domain.acl` import and the schemas import, and add the vector store import:

```python
from app.domain.acl import CONFIDENTIALITY_RANK, confidentiality_rank
from app.domain.vector import FakeVectorStore, VectorQuery, build_acl_filter, get_vector_store
```

And add `DocumentAclUpdate` to the existing `from app.domain.schemas import (...)` block.

- [ ] **Step 4: Add the endpoint** to `apps/api/app/api/v1/knowledge.py` (after `register_document`, before the upload route):

```python
@router.patch("/documents/{document_id}/acl", response_model=DocumentRead)
def update_document_acl(
    document_id: str,
    payload: DocumentAclUpdate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if payload.confidentiality_level.lower() not in CONFIDENTIALITY_RANK:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unknown confidentiality_level",
        )

    before = {
        "access_groups": list(document.access_groups),
        "confidentiality_level": document.confidentiality_level,
    }
    new_groups = list(dict.fromkeys(g.strip() for g in payload.access_groups if g.strip()))
    if not new_groups:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="access_groups must not be empty",
        )

    document.access_groups = new_groups
    document.confidentiality_level = payload.confidentiality_level.lower()
    rank = confidentiality_rank(document.confidentiality_level)

    for chunk in document.chunks:
        snapshot = dict(chunk.acl_snapshot or {})
        snapshot["access_groups"] = new_groups
        snapshot["confidentiality_level"] = document.confidentiality_level
        chunk.acl_snapshot = snapshot

    db.flush()
    # Fail-closed: if Qdrant sync raises, the whole request rolls back.
    chunks_synced = get_vector_store().set_document_acl(
        document.id, access_groups=tuple(new_groups), confidentiality_rank=rank
    )

    write_audit_event(
        db,
        principal=principal,
        event_type="document.acl_changed",
        target_type="document",
        target_id=document.id,
        reason=payload.reason,
        payload={
            "before": before,
            "after": {
                "access_groups": new_groups,
                "confidentiality_level": document.confidentiality_level,
            },
            "chunks_synced": chunks_synced,
        },
    )
    db.commit()
    db.refresh(document)
    return document
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests/test_acl_update_contracts.py -v`
Expected: all passed

- [ ] **Step 6: Commit**

```bash
git add apps/api/app/api/v1/knowledge.py apps/api/tests/test_acl_update_contracts.py
git commit -m "feat(api): PATCH document ACL with revocation propagation + audit"
```

---

### Task 4: Full suite green + ruff + security-review

**Files:** none (verification)

- [ ] **Step 1: Move `.env` aside and run the full suite**

```powershell
Move-Item apps/api/.env apps/api/.env.bak
apps/api/.venv/Scripts/python.exe -m pytest apps/api -q
Move-Item apps/api/.env.bak apps/api/.env
```
Expected: `85 passed` (baseline 81 + 4 new test functions counted; confirm 0 skipped, all green). If the count differs, reconcile — never leave a skip.

- [ ] **Step 2: ruff**

Run: `apps/api/.venv/Scripts/python.exe -m ruff check apps/api/app apps/api/tests`
Expected: clean (fix any issues).

- [ ] **Step 3: security-review on the ACL path**

Invoke the `security-review` skill scoped to the diff (ACL change path: endpoint, schema, vector payload sync). Address any real findings.

- [ ] **Step 4: Commit any fixes**

```bash
git add -A && git commit -m "chore: ruff + review fixes for ACL editing"
```

---

### Task 5: Live verification (real Qdrant) + docs

**Files:**
- Modify: `docs/superpowers/specs/2026-06-14-document-acl-edit-revocation-design.md` (append a "Live verification" section) OR add a results note to ONBOARDING/relevant doc.

- [ ] **Step 1: Start the live stack**

```powershell
docker start agentforge-ollama compose-postgres-1 compose-qdrant-1
```

- [ ] **Step 2: (Re)start the API** (no `--reload`; clear port 8000 if a stale python holds it). Confirm `.env` = qdrant + bge-m3 + agentforge_mvp2 + `AGENT_FORGE_RETRIEVAL_MIN_SCORE=0.53`.

- [ ] **Step 3: Live revocation run.** Pick (or upload+index) a real document in `chunks_active`. With the owning principal headers:
  1. Run a query via `/api/v1/knowledge/retrieval/preview` that returns the doc → record hit count + that the doc title appears.
  2. `PATCH /documents/{id}/acl` to a group the principal is NOT in, with a `reason`.
  3. Re-run the same query → confirm the doc is gone and `denied_count` increased.
  4. Confirm a `document.acl_changed` audit row exists with the `reason` and before/after.

- [ ] **Step 4: Write a "Live verification" section** into the design doc recording: before-hit count, after-hit count, denied_count delta, and the audit row id/reason. Be honest about what was and wasn't measured.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/specs/2026-06-14-document-acl-edit-revocation-design.md
git commit -m "docs: live verification of ACL revocation propagation"
```

---

### Task 6: Finish the branch (push + PR + merge)

- [ ] Use `superpowers:finishing-a-development-branch`: push, open PR (summary + test evidence + live results), request review, merge to `main`.
- [ ] After merge: `memory:remember` the ACL revocation mechanism, and write the next handoff prompt (slice 2/4: cleanup — MinIO/old eval harness/pgvector docs).

---

## Self-Review

**Spec coverage:**
- PATCH endpoint + set semantics + required reason → Task 2, 3. ✓
- Qdrant payload sync (no re-embed) → Task 1. ✓
- `DocumentChunk.acl_snapshot` consistency → Task 3 Step 4. ✓
- Audit `document.acl_changed` with before/after + reason → Task 3 + audit test. ✓
- Fail-closed on sync error → Task 3 (sync inside the same transaction, before commit). ✓
- Validation 422 (empty groups, bad confidentiality, missing reason) + 404 → Task 2, 3. ✓
- Full suite green + ruff + security-review → Task 4. ✓
- Live verification + docs → Task 5. ✓
- Finish branch + memory + handoff → Task 6. ✓

**Placeholder scan:** All code steps contain full code. The audit test has two versions in Task 3 (Step 1 loose + Step 1b strict); the plan explicitly says keep only the Step 1b version. No TODOs.

**Type consistency:** `set_document_acl(document_id, *, access_groups: tuple[str,...], confidentiality_rank: int) -> int` used identically in vector.py Protocol, FakeVectorStore, QdrantVectorStore, and the endpoint call site. `DocumentAclUpdate` fields (`access_groups`, `confidentiality_level`, `reason`) consistent across schema, endpoint, and tests. `CONFIDENTIALITY_RANK` imported from `app.domain.acl` (confirmed it exists there).

**Note on test count:** baseline is "64 passed" per CLAUDE.md but the handoff says "baseline 81". Task 4 Step 1 must reconcile the actual observed baseline before adding 4 — record the real number, don't assume.
