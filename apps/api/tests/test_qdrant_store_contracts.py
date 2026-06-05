from qdrant_client import QdrantClient

from app.core.principal import Principal
from app.domain.vector import VectorQuery, VectorUpsertInput, build_acl_filter
from app.infra.qdrant_store import QdrantVectorStore, build_qdrant_acl_filter, payload_allows


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
    # confidential (rank 3) excluded even for a confidential-clearance principal
    conf_acl = build_acl_filter(_principal(clearance="confidential"))
    assert payload_allows({**ok, "confidentiality_rank": 3}, conf_acl) is False


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


def test_qdrant_group_filter_excludes_even_when_clearance_allows():
    # rank 1 (internal) doc the principal COULD read by clearance, but the group
    # does not intersect -> must be excluded by the in-query group filter alone.
    store = _store()
    _upsert(store, chunk_id="hr2:1", document_id="hr2", content="finance policy",
            groups=("department:HR",), rank=1, title="HRInternal")
    result = store.search(
        query=VectorQuery(query_text="finance policy", top_k=10),
        documents=[],
        acl_filter=build_acl_filter(_principal()),
    )
    assert result.hits == ()


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
