# 진짜 벡터검색 (Qdrant + bge-m3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기존 `VectorStore` Protocol에 진짜 Qdrant 어댑터를 끼워, fake 키워드 검색을 bge-m3 임베딩 기반 의미 벡터검색으로 교체한다(ACL은 Qdrant payload 필터로 인-쿼리 적용).

**Architecture:** LLM 게이트웨이 패턴(env 주입 + 팩토리 + Protocol)을 그대로 따른다. `EmbeddingGateway`(OpenAI 호환 `/v1/embeddings`)와 `QdrantVectorStore`를 추가하고, `get_vector_store()` 팩토리가 env로 fake↔qdrant를 전환한다. 기본값은 `fake`라 기존 테스트는 무영향.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, httpx, `qdrant-client`(로컬 `:memory:` 모드로 테스트), Ollama(bge-m3) 로컬 검증.

**실행 환경:** 모든 테스트/명령은 `apps/api/.venv/Scripts/python.exe` 사용. 작업 디렉터리는 `apps/api`. 브랜치 `feat/real-vector-retrieval`.

---

## File Structure

- **신규** `app/services/embedding_gateway.py` — OpenAI 호환 임베딩 클라이언트 + `get_embedding_gateway()`
- **신규** `app/infra/qdrant_store.py` — `QdrantVectorStore`(Protocol 구현) + `build_qdrant_acl_filter` + `_payload_allows`
- **수정** `app/domain/vector.py` — `VectorUpsertInput` optional 필드 확장 + `get_vector_store()` 팩토리
- **수정** `app/core/config.py` — 임베딩/Qdrant/backend env 필드
- **수정** `app/domain/indexing.py` — 팩토리 사용 + 확장 필드로 upsert
- **수정** `app/api/v1/runs.py` — `get_vector_store()` 사용 + 검색 폴백 + degraded 트레이스
- **수정** `apps/api/pyproject.toml` — `qdrant-client` 의존성
- **신규 테스트** `tests/test_embedding_gateway_contracts.py`, `tests/test_qdrant_store_contracts.py`, `tests/test_vector_store_factory.py`

---

## Task 1: 설정 필드 + qdrant-client 의존성

**Files:**
- Modify: `app/core/config.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: `Settings`에 env 필드 추가**

`app/core/config.py`의 `Settings` 클래스에 기존 `llm_*` 필드 아래로 추가:

```python
    embedding_base_url: str | None = None
    embedding_model: str = "bge-m3"
    embedding_dim: int = 1024
    embedding_timeout_seconds: float = 30.0
    qdrant_url: str = "http://localhost:6333"
    vector_backend: str = "fake"  # "fake" | "qdrant"
```

- [ ] **Step 2: `pyproject.toml`에 의존성 추가**

`[project] dependencies` 리스트에 추가:

```toml
    "qdrant-client>=1.11,<2.0",
```

- [ ] **Step 3: .venv에 설치**

Run: `.venv\Scripts\python.exe -m pip install "qdrant-client>=1.11,<2.0"`
Expected: `Successfully installed qdrant-client-...`

- [ ] **Step 4: import 스모크 + 기존 테스트 무영향 확인**

Run: `.venv\Scripts\python.exe -c "import qdrant_client; from app.core.config import Settings; print(Settings().vector_backend)"`
Expected: `fake`

- [ ] **Step 5: Commit**

```bash
git add app/core/config.py pyproject.toml
git commit -m "feat(api): add embedding/qdrant settings and qdrant-client dep"
```

---

## Task 2: EmbeddingGateway (OpenAI 호환 /v1/embeddings)

**Files:**
- Create: `app/services/embedding_gateway.py`
- Test: `tests/test_embedding_gateway_contracts.py`

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_embedding_gateway_contracts.py`:

```python
import httpx
import pytest

from app.services.embedding_gateway import (
    EmbeddingGateway,
    EmbeddingUnavailable,
)


def test_not_configured_raises():
    gw = EmbeddingGateway(base_url=None, model="bge-m3", dim=1024, timeout_seconds=5)
    with pytest.raises(EmbeddingUnavailable):
        gw.embed(["hello"])


def test_embed_calls_openai_endpoint(monkeypatch):
    captured = {}

    def fake_post(self, url, json, **kwargs):
        captured["url"] = url
        captured["json"] = json
        return httpx.Response(
            200,
            json={"data": [{"embedding": [0.1, 0.2, 0.3]}, {"embedding": [0.4, 0.5, 0.6]}]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    gw = EmbeddingGateway(base_url="http://x/v1", model="bge-m3", dim=3, timeout_seconds=5)
    vectors = gw.embed(["a", "b"])

    assert vectors == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    assert captured["url"].endswith("/embeddings")
    assert captured["json"]["model"] == "bge-m3"
    assert captured["json"]["input"] == ["a", "b"]


def test_http_error_raises_unavailable(monkeypatch):
    def boom(self, url, json, **kwargs):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx.Client, "post", boom)
    gw = EmbeddingGateway(base_url="http://x/v1", model="m", dim=3, timeout_seconds=5)
    with pytest.raises(EmbeddingUnavailable):
        gw.embed(["a"])


def test_empty_input_returns_empty_without_call():
    gw = EmbeddingGateway(base_url="http://x/v1", model="m", dim=3, timeout_seconds=5)
    assert gw.embed([]) == []
```

- [ ] **Step 2: 실패 확인**

Run: `.venv\Scripts\python.exe -m pytest tests/test_embedding_gateway_contracts.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.embedding_gateway'`

- [ ] **Step 3: 구현**

`app/services/embedding_gateway.py`:

```python
from __future__ import annotations

import logging

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class EmbeddingUnavailable(RuntimeError):
    """Raised when the embedding endpoint is unset or unreachable."""


class EmbeddingGateway:
    """Gateway to an OpenAI-compatible embeddings endpoint.

    base_url must include the OpenAI version prefix, e.g. ``http://host:11434/v1``.
    """

    def __init__(self, base_url: str | None, model: str, dim: int, timeout_seconds: float) -> None:
        self.base_url = base_url.rstrip("/") if base_url else None
        self.model = model
        self.dim = dim
        self.timeout_seconds = timeout_seconds

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not self.base_url:
            raise EmbeddingUnavailable("embedding base_url is not configured")
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                r = client.post(
                    f"{self.base_url}/embeddings",
                    json={"model": self.model, "input": texts},
                )
                r.raise_for_status()
                data = r.json()["data"]
                return [item["embedding"] for item in data]
        except Exception as exc:  # noqa: BLE001 - normalize to a domain error
            logger.warning("embedding call failed: %s", exc)
            raise EmbeddingUnavailable(str(exc)) from exc


def get_embedding_gateway() -> EmbeddingGateway:
    s = get_settings()
    return EmbeddingGateway(
        base_url=s.embedding_base_url,
        model=s.embedding_model,
        dim=s.embedding_dim,
        timeout_seconds=s.embedding_timeout_seconds,
    )
```

- [ ] **Step 4: 통과 확인**

Run: `.venv\Scripts\python.exe -m pytest tests/test_embedding_gateway_contracts.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add app/services/embedding_gateway.py tests/test_embedding_gateway_contracts.py
git commit -m "feat(api): add OpenAI-compatible embedding gateway"
```

---

## Task 3: VectorUpsertInput 확장 (optional 필드)

**Files:**
- Modify: `app/domain/vector.py:30-43`
- Test: `tests/test_vector_adapter_contracts.py` (기존 + 1개 추가)

- [ ] **Step 1: 기존 동작 보존 + 신규 필드 기본값 테스트 추가**

`tests/test_vector_adapter_contracts.py` 맨 아래에 추가:

```python
def test_upsert_input_new_fields_are_optional():
    from app.domain.vector import VectorUpsertInput

    minimal = VectorUpsertInput(
        chunk_id="d:chunk-001",
        document_id="d",
        content_hash="sha256-d",
        embedding_model="none-smoke",
    )
    assert minimal.content == ""
    assert minimal.access_groups == ()
    assert minimal.confidentiality_rank == 1
    assert minimal.knowledge_source_id == ""
```

- [ ] **Step 2: 실패 확인**

Run: `.venv\Scripts\python.exe -m pytest tests/test_vector_adapter_contracts.py::test_upsert_input_new_fields_are_optional -q`
Expected: FAIL — `AttributeError: 'VectorUpsertInput' object has no attribute 'content'`

- [ ] **Step 3: 필드 추가**

`app/domain/vector.py`의 `VectorUpsertInput`를 교체:

```python
@dataclass(frozen=True)
class VectorUpsertInput:
    chunk_id: str
    document_id: str
    content_hash: str
    embedding_model: str
    content: str = ""
    title: str = ""
    section_path: tuple[str, ...] = ()
    citation_locator: str = ""
    access_groups: tuple[str, ...] = ()
    confidentiality_rank: int = 1
    knowledge_source_id: str = ""
```

- [ ] **Step 4: 전체 벡터 계약 테스트 통과 확인**

Run: `.venv\Scripts\python.exe -m pytest tests/test_vector_adapter_contracts.py -q`
Expected: PASS (기존 + 신규, 모두 통과)

- [ ] **Step 5: Commit**

```bash
git add app/domain/vector.py tests/test_vector_adapter_contracts.py
git commit -m "feat(api): extend VectorUpsertInput with optional embedding/ACL fields"
```

---

## Task 4: Qdrant ACL 필터 빌더 + payload 불변식 (순수 함수)

**Files:**
- Create: `app/infra/qdrant_store.py` (이 태스크에서 순수 함수만 먼저)
- Test: `tests/test_qdrant_store_contracts.py`

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_qdrant_store_contracts.py`:

```python
from app.core.principal import Principal
from app.domain.vector import build_acl_filter
from app.infra.qdrant_store import build_qdrant_acl_filter, payload_allows


def _principal(clearance="internal", groups=("all-employees",), department="Finance"):
    return Principal(
        user_id="u1", department=department, roles=("employee",),
        groups=groups, clearance_level=clearance,
    )


def test_filter_has_status_clearance_and_group_conditions():
    acl = build_acl_filter(_principal())
    flt = build_qdrant_acl_filter(acl, knowledge_source_ids=("source-1",))
    keys = [c.key for c in flt.must]
    assert "status" in keys
    assert "confidentiality_rank" in keys
    assert "knowledge_source_id" in keys
    assert "access_groups" in keys


def test_payload_allows_matches_acl_semantics():
    acl = build_acl_filter(_principal())
    ok = {
        "status": "indexed", "confidentiality_rank": 1,
        "access_groups": ["all-employees"], "knowledge_source_id": "source-1",
    }
    assert payload_allows(ok, acl) is True

    # group mismatch -> deny
    assert payload_allows({**ok, "access_groups": ["department:HR"]}, acl) is False
    # empty groups -> deny-by-default
    assert payload_allows({**ok, "access_groups": []}, acl) is False
    # clearance too low -> deny
    assert payload_allows({**ok, "confidentiality_rank": 2}, acl) is False
    # not indexed -> deny
    assert payload_allows({**ok, "status": "registered"}, acl) is False
```

- [ ] **Step 2: 실패 확인**

Run: `.venv\Scripts\python.exe -m pytest tests/test_qdrant_store_contracts.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.infra.qdrant_store'`

- [ ] **Step 3: 순수 함수 구현**

`app/infra/qdrant_store.py` (이 태스크 분량만; 클래스는 Task 5에서 같은 파일에 추가):

```python
from __future__ import annotations

import logging

from qdrant_client import models as qm

from app.domain.acl import (
    EXCLUDED_INDEX_CONFIDENTIALITY_LEVELS,
    SEARCHABLE_DOCUMENT_STATUSES,
    confidentiality_rank,
)
from app.domain.vector import AclFilter

logger = logging.getLogger(__name__)


def build_qdrant_acl_filter(acl: AclFilter, knowledge_source_ids: tuple[str, ...]) -> qm.Filter:
    clearance = confidentiality_rank(acl.clearance_level)
    must: list[qm.FieldCondition] = [
        qm.FieldCondition(key="status", match=qm.MatchValue(value="indexed")),
        qm.FieldCondition(key="confidentiality_rank", range=qm.Range(lte=clearance)),
        qm.FieldCondition(key="access_groups", match=qm.MatchAny(any=list(acl.subjects))),
    ]
    if knowledge_source_ids:
        must.append(
            qm.FieldCondition(
                key="knowledge_source_id",
                match=qm.MatchAny(any=list(knowledge_source_ids)),
            )
        )
    return qm.Filter(must=must)


def payload_allows(payload: dict, acl: AclFilter) -> bool:
    """Defense-in-depth re-check mirroring app.domain.acl.principal_can_access_document."""
    if payload.get("status") not in SEARCHABLE_DOCUMENT_STATUSES:
        return False
    level_rank = int(payload.get("confidentiality_rank", confidentiality_rank("confidential")))
    if level_rank >= confidentiality_rank("confidential") and "confidential" in EXCLUDED_INDEX_CONFIDENTIALITY_LEVELS:
        # confidential excluded from MVP index entirely
        if level_rank == confidentiality_rank("confidential"):
            return False
    if level_rank > confidentiality_rank(acl.clearance_level):
        return False
    groups = payload.get("access_groups") or []
    if not groups:
        return False
    return bool(set(groups).intersection(acl.subjects))
```

- [ ] **Step 4: 통과 확인**

Run: `.venv\Scripts\python.exe -m pytest tests/test_qdrant_store_contracts.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add app/infra/qdrant_store.py tests/test_qdrant_store_contracts.py
git commit -m "feat(api): add Qdrant ACL filter builder and payload invariant"
```

---

## Task 5: QdrantVectorStore (upsert / search / delete) — 계약 동치

**Files:**
- Modify: `app/infra/qdrant_store.py` (클래스 추가)
- Test: `tests/test_qdrant_store_contracts.py` (추가)

Qdrant 로컬 `:memory:` 모드로 외부 서비스 없이 테스트한다. 임베딩은 테스트에서 결정적 stub 함수를 주입한다.

- [ ] **Step 1: 실패 테스트 작성 (Fake↔Qdrant ACL 동치 + delete)**

`tests/test_qdrant_store_contracts.py`에 추가:

```python
from qdrant_client import QdrantClient

from app.domain.vector import VectorQuery, VectorUpsertInput
from app.infra.qdrant_store import QdrantVectorStore


def _stub_embed(texts):
    # 결정적: 단어 'policy','manager','finance','hr'의 등장 횟수로 4차원 벡터
    vocab = ["policy", "manager", "finance", "hr"]
    out = []
    for t in texts:
        low = t.casefold()
        out.append([float(low.count(w)) + 0.01 for w in vocab])
    return out


def _store():
    client = QdrantClient(":memory:")
    return QdrantVectorStore(client=client, embed=_stub_embed, dim=4, collection="chunks_active")


def _upsert(store, *, chunk_id, document_id, content, ks="source-1",
            groups=("all-employees",), rank=1, title="T"):
    store.upsert_chunks((
        VectorUpsertInput(
            chunk_id=chunk_id, document_id=document_id, content_hash="h",
            embedding_model="stub", content=content, title=title,
            citation_locator=f"{title} / lines 1-1",
            access_groups=tuple(groups), confidentiality_rank=rank,
            knowledge_source_id=ks,
        ),
    ))


def test_qdrant_search_excludes_unauthorized_groups():
    store = _store()
    _upsert(store, chunk_id="pub:1", document_id="pub", content="company policy", groups=("all-employees",))
    _upsert(store, chunk_id="hr:1", document_id="hr", content="hr manager policy",
            groups=("department:HR",), rank=2, title="HR")

    result = store.search(
        query=VectorQuery(query_text="policy", top_k=10),
        documents=[],
        acl_filter=build_acl_filter(_principal()),
    )
    ids = [h.document_id for h in result.hits]
    assert "pub" in ids
    assert "hr" not in ids


def test_qdrant_empty_groups_denied_by_default():
    store = _store()
    _upsert(store, chunk_id="draft:1", document_id="draft", content="policy", groups=())
    result = store.search(
        query=VectorQuery(query_text="policy", top_k=10),
        documents=[],
        acl_filter=build_acl_filter(_principal()),
    )
    assert result.hits == ()


def test_qdrant_delete_document_removes_hits():
    store = _store()
    _upsert(store, chunk_id="d:1", document_id="d", content="policy")
    store.delete_document("d")
    result = store.search(
        query=VectorQuery(query_text="policy", top_k=10),
        documents=[],
        acl_filter=build_acl_filter(_principal()),
    )
    assert result.hits == ()


def test_qdrant_returns_citation_and_chunk_metadata():
    store = _store()
    _upsert(store, chunk_id="d:1", document_id="d", content="finance policy", title="Finance")
    result = store.search(
        query=VectorQuery(query_text="finance", top_k=5),
        documents=[],
        acl_filter=build_acl_filter(_principal()),
    )
    assert result.hits
    hit = result.hits[0]
    assert hit.chunk_id == "d:1"
    assert hit.citation_locator == "Finance / lines 1-1"
    assert hit.title == "Finance"
```

- [ ] **Step 2: 실패 확인**

Run: `.venv\Scripts\python.exe -m pytest tests/test_qdrant_store_contracts.py -q`
Expected: FAIL — `ImportError: cannot import name 'QdrantVectorStore'`

- [ ] **Step 3: 클래스 구현**

`app/infra/qdrant_store.py` 상단 import에 추가하고(`from collections.abc import Callable, Sequence`, `from app.domain.vector import VectorHit, VectorQuery, VectorSearchResult, VectorUpsertInput, VectorUpsertResult`), 파일 끝에 추가:

```python
class QdrantVectorStore:
    """Real vector store over Qdrant. ACL applied as an in-query payload filter."""

    def __init__(self, *, client, embed: Callable[[list[str]], list[list[float]]],
                 dim: int, collection: str = "chunks_active") -> None:
        self._client = client
        self._embed = embed
        self._dim = dim
        self._collection = collection

    def _ensure_collection(self) -> None:
        from qdrant_client import models as qm

        if self._client.collection_exists(self._collection):
            return
        self._client.create_collection(
            collection_name=self._collection,
            vectors_config=qm.VectorParams(size=self._dim, distance=qm.Distance.COSINE),
        )

    def upsert_chunks(self, chunks: Sequence[VectorUpsertInput]) -> tuple[VectorUpsertResult, ...]:
        from qdrant_client import models as qm

        chunks = tuple(chunks)
        if not chunks:
            return ()
        self._ensure_collection()
        texts = [f"{c.title}\n{' / '.join(c.section_path)}\n{c.content}".strip() for c in chunks]
        vectors = self._embed(texts)
        points = [
            qm.PointStruct(
                id=_point_id(c.chunk_id),
                vector=vec,
                payload={
                    "chunk_id": c.chunk_id,
                    "document_id": c.document_id,
                    "knowledge_source_id": c.knowledge_source_id,
                    "title": c.title,
                    "citation_locator": c.citation_locator,
                    "access_groups": list(c.access_groups),
                    "confidentiality_rank": c.confidentiality_rank,
                    "status": "indexed",
                    "content_hash": c.content_hash,
                },
            )
            for c, vec in zip(chunks, vectors, strict=True)
        ]
        self._client.upsert(collection_name=self._collection, points=points)
        return tuple(
            VectorUpsertResult(chunk_id=c.chunk_id, vector_ref=f"qdrant:{self._collection}:{c.chunk_id}")
            for c in chunks
        )

    def search(self, *, query: VectorQuery, documents, acl_filter) -> VectorSearchResult:
        if not self._client.collection_exists(self._collection):
            return VectorSearchResult(hits=(), denied_count=0)
        query_vector = self._embed([query.query_text])[0]
        acl_q = build_qdrant_acl_filter(acl_filter, query.knowledge_source_ids)
        found = self._client.search(
            collection_name=self._collection,
            query_vector=query_vector,
            query_filter=acl_q,
            limit=query.top_k,
            with_payload=True,
        )
        hits: list[VectorHit] = []
        for rank, point in enumerate(found, start=1):
            payload = point.payload or {}
            if not payload_allows(payload, acl_filter):  # defense-in-depth
                logger.warning("dropping ACL-violating hit chunk_id=%s", payload.get("chunk_id"))
                continue
            hits.append(
                VectorHit(
                    document_id=payload["document_id"],
                    knowledge_source_id=payload.get("knowledge_source_id", ""),
                    title=payload.get("title", ""),
                    confidentiality_level="",
                    access_groups=tuple(payload.get("access_groups", [])),
                    score=float(point.score),
                    citation=payload.get("citation_locator", ""),
                    rank_original=rank,
                    chunk_id=payload.get("chunk_id"),
                    citation_locator=payload.get("citation_locator"),
                    content_hash=payload.get("content_hash"),
                    vector_ref=f"qdrant:{self._collection}:{payload.get('chunk_id')}",
                )
            )
        denied_count = self._denied_count(query, acl_filter, allowed=len(hits))
        return VectorSearchResult(hits=tuple(hits), denied_count=denied_count)

    def _denied_count(self, query: VectorQuery, acl_filter, allowed: int) -> int:
        from qdrant_client import models as qm

        must = [qm.FieldCondition(key="status", match=qm.MatchValue(value="indexed"))]
        if query.knowledge_source_ids:
            must.append(
                qm.FieldCondition(
                    key="knowledge_source_id",
                    match=qm.MatchAny(any=list(query.knowledge_source_ids)),
                )
            )
        try:
            total = self._client.count(
                collection_name=self._collection,
                count_filter=qm.Filter(must=must),
                exact=True,
            ).count
        except Exception:  # noqa: BLE001 - count is a best-effort audit signal
            return 0
        return max(0, total - allowed)

    def delete_document(self, document_id: str) -> None:
        from qdrant_client import models as qm

        if not self._client.collection_exists(self._collection):
            return
        self._client.delete(
            collection_name=self._collection,
            points_selector=qm.FilterSelector(
                filter=qm.Filter(
                    must=[qm.FieldCondition(key="document_id", match=qm.MatchValue(value=document_id))]
                )
            ),
        )


def _point_id(chunk_id: str) -> str:
    import uuid

    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))
```

(주의: Qdrant point id는 UUID 또는 정수만 허용하므로 `chunk_id`를 UUID5로 결정적 변환한다. `chunk_id` 원본은 payload에 보존한다.)

- [ ] **Step 4: 통과 확인**

Run: `.venv\Scripts\python.exe -m pytest tests/test_qdrant_store_contracts.py -q`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add app/infra/qdrant_store.py tests/test_qdrant_store_contracts.py
git commit -m "feat(api): add QdrantVectorStore with in-query ACL filter + invariant"
```

---

## Task 6: get_vector_store() 팩토리 (env 전환)

**Files:**
- Modify: `app/domain/vector.py` (파일 끝에 팩토리 추가)
- Test: `tests/test_vector_store_factory.py`

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_vector_store_factory.py`:

```python
import pytest

from app.core.config import get_settings
from app.domain.vector import FakeVectorStore, get_vector_store


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_default_backend_is_fake(monkeypatch):
    monkeypatch.delenv("AGENT_FORGE_VECTOR_BACKEND", raising=False)
    assert isinstance(get_vector_store(), FakeVectorStore)


def test_qdrant_backend_without_embedding_url_falls_back_to_fake(monkeypatch):
    monkeypatch.setenv("AGENT_FORGE_VECTOR_BACKEND", "qdrant")
    monkeypatch.delenv("AGENT_FORGE_EMBEDDING_BASE_URL", raising=False)
    assert isinstance(get_vector_store(), FakeVectorStore)


def test_qdrant_backend_with_config_returns_qdrant(monkeypatch):
    monkeypatch.setenv("AGENT_FORGE_VECTOR_BACKEND", "qdrant")
    monkeypatch.setenv("AGENT_FORGE_EMBEDDING_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("AGENT_FORGE_QDRANT_URL", "http://localhost:6333")
    from app.infra.qdrant_store import QdrantVectorStore

    assert isinstance(get_vector_store(), QdrantVectorStore)
```

- [ ] **Step 2: 실패 확인**

Run: `.venv\Scripts\python.exe -m pytest tests/test_vector_store_factory.py -q`
Expected: FAIL — `ImportError: cannot import name 'get_vector_store'`

- [ ] **Step 3: 팩토리 구현**

`app/domain/vector.py` 파일 끝에 추가(QdrantVectorStore/EmbeddingGateway는 함수 내부에서 지연 import — domain→infra/services 순환 방지):

```python
def get_vector_store() -> "VectorStore":
    from app.core.config import get_settings

    s = get_settings()
    if s.vector_backend == "qdrant" and s.embedding_base_url:
        from qdrant_client import QdrantClient

        from app.infra.qdrant_store import QdrantVectorStore
        from app.services.embedding_gateway import get_embedding_gateway

        gateway = get_embedding_gateway()
        client = QdrantClient(url=s.qdrant_url)
        return QdrantVectorStore(
            client=client, embed=gateway.embed, dim=s.embedding_dim, collection="chunks_active"
        )
    return FakeVectorStore()
```

`app/domain/vector.py` 상단 import에 `get_settings`는 추가하지 않는다(함수 내 지연 import 유지). 파일 맨 위 `from __future__ import annotations`가 이미 있으므로 반환 타입 문자열 주석은 그대로 동작한다.

- [ ] **Step 4: 통과 확인**

Run: `.venv\Scripts\python.exe -m pytest tests/test_vector_store_factory.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add app/domain/vector.py tests/test_vector_store_factory.py
git commit -m "feat(api): add env-driven get_vector_store factory"
```

---

## Task 7: 색인 파이프라인을 팩토리 + 확장 필드로 연결

**Files:**
- Modify: `app/domain/indexing.py:97-108` (upsert 구성)
- Test: `tests/test_runtime_contracts.py` (기존 그린 유지로 회귀 확인)

색인은 기본 backend=fake이므로 동작/결과가 동일해야 한다(회귀 0). 단 upsert에 확장 필드를 채워 Qdrant 사용 시 payload가 완전해지도록 한다.

- [ ] **Step 1: upsert 구성 교체**

`app/domain/indexing.py`에서 `from app.domain.vector import FakeVectorStore, VectorUpsertInput`를 `from app.domain.vector import VectorUpsertInput, get_vector_store`로 바꾸고, `acl_snapshot` 정의 직후의 `upsert_results = FakeVectorStore().upsert_chunks(...)` 블록을 다음으로 교체:

```python
    confidentiality_rank_value = confidentiality_rank(document.confidentiality_level)
    upsert_results = get_vector_store().upsert_chunks(
        tuple(
            VectorUpsertInput(
                chunk_id=parsed_chunk.chunk_id,
                document_id=document.id,
                content_hash=parsed_chunk.content_hash,
                embedding_model=embedding_model,
                content=parsed_chunk.content,
                title=document.title,
                section_path=tuple(parsed_chunk.section_path),
                citation_locator=parsed_chunk.citation_locator,
                access_groups=tuple(document.access_groups),
                confidentiality_rank=confidentiality_rank_value,
                knowledge_source_id=document.knowledge_source_id,
            )
            for parsed_chunk in parsed_chunks
        )
    )
```

그리고 파일 상단 import에 `from app.domain.acl import confidentiality_rank, document_can_be_indexed`로 `confidentiality_rank`를 추가(기존 `document_can_be_indexed`와 합침).

- [ ] **Step 2: 색인 실패 시 job failed 처리 (Qdrant/임베딩 오류)**

위 `upsert_results = ...` 호출을 try/except로 감싼다:

```python
    try:
        confidentiality_rank_value = confidentiality_rank(document.confidentiality_level)
        upsert_results = get_vector_store().upsert_chunks(
            ...  # (Step 1의 동일 내용)
        )
    except Exception as exc:  # noqa: BLE001 - fail the job, never store half-indexed chunks
        job.status = "failed"
        job.error_code = "VECTOR_UPSERT_FAILED"
        job.error_message = str(exc)
        job.finished_at = datetime.now(UTC)
        document.status = "index_failed"
        write_audit_event(
            db, principal=principal, event_type="document.index_failed",
            target_type="document", target_id=document.id,
            payload={"index_job_id": job.id, "error_code": job.error_code},
        )
        return
```

- [ ] **Step 3: 회귀 확인 (기본 fake 경로, 색인/시드 테스트)**

Run: `.venv\Scripts\python.exe -m pytest tests/test_seed_demo.py tests/test_runtime_contracts.py -q`
Expected: PASS (변경 전과 동일하게 모두 통과)

- [ ] **Step 4: Commit**

```bash
git add app/domain/indexing.py
git commit -m "feat(api): index via vector-store factory with full ACL payload"
```

---

## Task 8: 런타임 검색을 팩토리 + 폴백 + degraded 트레이스로 연결

**Files:**
- Modify: `app/api/v1/runs.py` (`_search_authorized_context`, retriever 스텝, acl_filter_snapshot)
- Test: `tests/test_runtime_contracts.py` (폴백 테스트 추가)

- [ ] **Step 1: 폴백 동작 테스트 추가**

`tests/test_runtime_contracts.py` 맨 아래에 추가(기존 `client` 픽스처 재사용):

```python
def test_run_falls_back_to_fake_when_vector_store_errors(client, monkeypatch):
    # Qdrant 경로가 검색 중 예외를 던져도 답변은 계속되고 degraded로 표기된다.
    import app.api.v1.runs as runs_module
    from app.domain.vector import FakeVectorStore

    class _Boom:
        def search(self, **kwargs):
            raise RuntimeError("qdrant down")

    calls = {"n": 0}
    real_fake = FakeVectorStore

    def fake_factory():
        calls["n"] += 1
        return _Boom() if calls["n"] == 1 else real_fake()

    monkeypatch.setattr(runs_module, "get_vector_store", fake_factory)

    source = _create_source(client)
    document = _register_document(
        client, source_id=source["id"], title="Remote Work Policy",
        confidentiality_level="internal", access_groups=["all-employees"],
    )
    _index_document(client, document_id=document["id"], source_text="remote work is allowed two days")
    agent = _publish_agent(client, knowledge_source_id=source["id"])

    run = _create_run(client, agent_id=agent["id"], message="remote work policy")
    steps = client.get(f"/api/v1/runs/{run['id']}/steps").json()
    retriever = next(s for s in steps if s["step_type"] == "retriever")
    assert retriever["output_summary"]["vector_adapter"] == "fake_fallback"
    assert retriever["output_summary"]["degraded"] is True
```

> 참고: `_create_source`, `_register_document`, `_index_document`, `_publish_agent`, `_create_run` 등 헬퍼는 이미 `tests/test_runtime_contracts.py`에 존재한다. 시그니처가 다르면 같은 파일의 기존 사용처를 그대로 따른다.

- [ ] **Step 2: 실패 확인**

Run: `.venv\Scripts\python.exe -m pytest tests/test_runtime_contracts.py::test_run_falls_back_to_fake_when_vector_store_errors -q`
Expected: FAIL — `vector_adapter` 이 `"fake"`이거나 `degraded` 키 없음

- [ ] **Step 3: 검색부 리팩터 + import 추가**

`app/api/v1/runs.py` 상단 import에서 `from app.domain.vector import FakeVectorStore, VectorQuery, VectorSearchResult, build_acl_filter`를 `from app.domain.vector import FakeVectorStore, VectorQuery, VectorSearchResult, build_acl_filter, get_vector_store`로 바꾼다.

`_search_authorized_context`를 교체(라벨을 함께 반환):

```python
def _search_authorized_context(
    *,
    db: Session,
    query_text: str,
    knowledge_source_ids: list[str],
    top_k: int,
    acl_filter,
) -> tuple[VectorSearchResult, str, bool]:
    documents = list(
        db.scalars(
            select(Document)
            .options(selectinload(Document.chunks))
            .order_by(Document.created_at.desc())
        )
    )
    query = VectorQuery(
        query_text=query_text,
        knowledge_source_ids=tuple(knowledge_source_ids),
        top_k=top_k,
    )
    store = get_vector_store()
    label = "qdrant" if not isinstance(store, FakeVectorStore) else "fake"
    try:
        result = store.search(query=query, documents=documents, acl_filter=acl_filter)
        return result, label, False
    except Exception as exc:  # noqa: BLE001 - stay answerable, ACL-safe, but mark degraded
        logger.warning("vector search failed (%s); falling back to FakeVectorStore", exc)
        result = FakeVectorStore().search(query=query, documents=documents, acl_filter=acl_filter)
        return result, "fake_fallback", True
```

`runs.py` 상단에 `import logging` 와 `logger = logging.getLogger(__name__)` 가 없으면 추가한다.

- [ ] **Step 4: 호출부 + 트레이스 반영**

`create_run` 안에서 `vector_result = _search_authorized_context(...)` 호출을 다음으로 교체:

```python
    vector_result, vector_adapter, vector_degraded = _search_authorized_context(
        db=db,
        query_text=payload.input.message,
        knowledge_source_ids=knowledge_source_ids,
        top_k=payload.top_k,
        acl_filter=acl_filter,
    )
```

retriever 스텝의 `output_summary`를 교체:

```python
        output_summary={
            "hit_count": len(vector_result.hits),
            "denied_count": vector_result.denied_count,
            "vector_adapter": vector_adapter,
            "degraded": vector_degraded,
        },
```

그리고 `RetrievalHit(...)` 생성 시 `acl_filter_snapshot`의 `"vector_adapter": "fake"`를 `"vector_adapter": vector_adapter`로 바꾼다.

- [ ] **Step 5: 통과 + 전체 회귀 확인**

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: PASS — 기존 40 + 신규 테스트, skip 0

- [ ] **Step 6: Commit**

```bash
git add app/api/v1/runs.py tests/test_runtime_contracts.py
git commit -m "feat(api): runtime search via factory with ACL-safe fallback + degraded trace"
```

---

## Task 9: 라이브 검증 (실제 Qdrant + bge-m3)

**Files:** 없음(수동 검증). 코드 변경 없음.

- [ ] **Step 1: 임베딩 모델 pull**

Run: `docker exec agentforge-ollama ollama pull bge-m3`
Expected: `success`

- [ ] **Step 2: Qdrant 컨테이너 확인/기동**

Run: `docker compose -f ../../deploy/compose/docker-compose.dev.yaml up -d qdrant`
그리고 `curl http://localhost:6333/readyz` → `all shards are ready`

- [ ] **Step 3: `apps/api/.env`에 벡터 backend 활성화 추가**

```
AGENT_FORGE_VECTOR_BACKEND=qdrant
AGENT_FORGE_EMBEDDING_BASE_URL=http://localhost:11434/v1
AGENT_FORGE_EMBEDDING_MODEL=bge-m3
AGENT_FORGE_EMBEDDING_DIM=1024
AGENT_FORGE_QDRANT_URL=http://localhost:6333
```

- [ ] **Step 4: 깨끗한 DB로 재색인(시드)**

새 검증 DB를 쓰거나 기존 `agentforge_mvp`를 재사용. API 기동 전 `python -m app.seed_demo` 로 재색인(이번엔 실제 bge-m3 임베딩이 Qdrant로 upsert됨).
Expected: `chunk_count >= 1`, 예외 없음. Qdrant에 점 생성: `curl http://localhost:6333/collections/chunks_active` → `points_count >= 1`.

- [ ] **Step 5: 라이브 질의 (의미검색 + ACL)**

API 기동 후, Finance(all-employees) 사용자로 "휴가 정책 알려줘" 질의 → 한국어 출처 답변, retriever 스텝 `vector_adapter="qdrant"`, 생성 스텝 `mode=llm`. 권한 없는 그룹 사용자 → 거부, `denied_count>=1`.

- [ ] **Step 6: 회귀 재확인 (.env 빼고)**

Task 8 Step 5와 동일하게 `.env`를 잠시 옆으로 치우고 `pytest -q` → 40+신규 그린, skip 0. 확인 후 `.env` 복원.

---

## Self-Review (작성자 확인 완료)

- **스펙 커버리지**: §2 컴포넌트(Task 2,5,6) / §3 데이터흐름(Task 7,8) / §4 ACL 필터+불변식(Task 4,5) / §5 폴백·색인실패(Task 7,8) / §6 테스트(Task 2,4,5,6,8) / §7 운영 env(Task 1,9) — 전부 태스크로 매핑됨.
- **플레이스홀더**: 모든 코드 스텝에 실제 코드 포함, TODO/TBD 없음.
- **타입 일관성**: `VectorUpsertInput` 신규 필드명(content/title/section_path/citation_locator/access_groups/confidentiality_rank/knowledge_source_id)이 Task 3 정의와 Task 5·7 사용처에서 동일. `get_vector_store`/`build_qdrant_acl_filter`/`payload_allows` 시그니처가 정의·사용 일치. `_search_authorized_context` 반환 튜플(result,label,degraded)이 Task 8 호출부와 일치.
