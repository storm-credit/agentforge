from types import SimpleNamespace

import pytest

from app.core.principal import Principal
from app.domain.vector import (
    FakeVectorStore,
    VectorQuery,
    VectorUpsertInput,
    build_acl_filter,
)


def _principal(
    *,
    user_id: str = "user-1",
    department: str = "Finance",
    clearance_level: str = "internal",
) -> Principal:
    return Principal(
        user_id=user_id,
        department=department,
        roles=("employee",),
        groups=("all-employees",),
        clearance_level=clearance_level,
    )


def _document(
    *,
    document_id: str,
    knowledge_source_id: str = "source-1",
    title: str,
    content: str,
    confidentiality_level: str = "internal",
    access_groups: list[str] | None = None,
    status: str = "indexed",
):
    access_groups = access_groups if access_groups is not None else ["all-employees"]
    chunk_id = f"{document_id}:chunk-001"
    chunk = SimpleNamespace(
        id=chunk_id,
        document_id=document_id,
        chunk_index=0,
        content=content,
        content_hash=f"sha256-{document_id}",
        vector_ref=f"fake-vector:none-smoke:{chunk_id}",
        status="indexed",
        citation_locator=f"{title} / body / lines 1-1",
    )
    return SimpleNamespace(
        id=document_id,
        knowledge_source_id=knowledge_source_id,
        title=title,
        confidentiality_level=confidentiality_level,
        access_groups=access_groups,
        status=status,
        effective_date=None,
        chunks=[chunk],
    )


def test_fake_vector_upsert_is_deterministic():
    store = FakeVectorStore()
    chunks = (
        VectorUpsertInput(
            chunk_id="doc-1:chunk-001",
            document_id="doc-1",
            content_hash="sha256-doc-1",
            embedding_model="none-smoke",
        ),
    )

    first = store.upsert_chunks(chunks)
    second = store.upsert_chunks(chunks)

    assert first == second
    assert first[0].vector_ref == "fake-vector:none-smoke:doc-1:chunk-001"


def test_search_requires_acl_filter_argument():
    store = FakeVectorStore()

    with pytest.raises(TypeError):
        store.search(query=VectorQuery(query_text="policy"), documents=[])


def test_fake_vector_search_filters_acl_before_ranking():
    allowed = _document(
        document_id="pub-1",
        title="Company Holiday Policy",
        content="company holiday policy for all employees",
    )
    forbidden = _document(
        document_id="hr-1",
        title="HR Leave Exception Policy",
        content="leave exception policy manager approval",
        confidentiality_level="restricted",
        access_groups=["department:HR"],
    )
    confidential = _document(
        document_id="exec-1",
        title="Executive Strategy",
        content="manager approval confidential plan",
        confidentiality_level="confidential",
        access_groups=["all-employees"],
    )
    no_acl = _document(
        document_id="draft-1",
        title="Draft Policy",
        content="policy draft",
        access_groups=[],
    )

    result = FakeVectorStore().search(
        query=VectorQuery(query_text="manager approval policy", top_k=10),
        documents=[forbidden, confidential, no_acl, allowed],
        acl_filter=build_acl_filter(_principal()),
    )

    assert [hit.document_id for hit in result.hits] == ["pub-1"]
    assert result.hits[0].acl_decision == "allow"
    assert result.denied_count == 3


def test_fake_vector_search_respects_knowledge_source_scope_and_delete():
    source_a = _document(
        document_id="doc-a",
        knowledge_source_id="source-a",
        title="Operations Policy",
        content="operations policy",
    )
    source_b = _document(
        document_id="doc-b",
        knowledge_source_id="source-b",
        title="Finance Policy",
        content="finance policy",
    )
    store = FakeVectorStore()

    scoped = store.search(
        query=VectorQuery(query_text="policy", knowledge_source_ids=("source-b",), top_k=10),
        documents=[source_a, source_b],
        acl_filter=build_acl_filter(_principal()),
    )

    assert [hit.document_id for hit in scoped.hits] == ["doc-b"]

    store.delete_document("doc-b")
    deleted = store.search(
        query=VectorQuery(query_text="policy", knowledge_source_ids=("source-b",), top_k=10),
        documents=[source_a, source_b],
        acl_filter=build_acl_filter(_principal()),
    )

    assert deleted.hits == ()


def test_fake_vector_search_excludes_zero_score_authorized_chunks():
    document = _document(
        document_id="doc-1",
        title="Remote Work Policy",
        content="employees may request remote work after manager approval",
    )

    result = FakeVectorStore().search(
        query=VectorQuery(query_text="travel reimbursement receipt"),
        documents=[document],
        acl_filter=build_acl_filter(_principal()),
    )

    assert result.hits == ()


def test_fake_vector_search_excludes_weak_single_term_overlap():
    allowed = _document(
        document_id="fin-public",
        title="Expense Reimbursement Policy",
        content="expense exception approval rules",
    )
    denied = _document(
        document_id="fin-close",
        title="Quarter Close Restricted Checklist",
        content="quarter close exception ledger restricted workflow",
        confidentiality_level="restricted",
        access_groups=["department:Finance"],
    )

    result = FakeVectorStore().search(
        query=VectorQuery(query_text="finance quarter close exception ledger", top_k=10),
        documents=[allowed, denied],
        acl_filter=build_acl_filter(_principal(department="HR")),
    )

    assert result.hits == ()
    assert result.denied_count == 1
