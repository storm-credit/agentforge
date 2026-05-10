from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from app.core.principal import Principal
from app.domain.acl import principal_acl_subjects, principal_can_access_document

if TYPE_CHECKING:
    from app.domain.models import Document


@dataclass(frozen=True)
class AclFilter:
    principal: Principal
    subjects: tuple[str, ...]
    clearance_level: str


@dataclass(frozen=True)
class VectorQuery:
    query_text: str
    knowledge_source_ids: tuple[str, ...] = ()
    top_k: int = 5
    collection_alias: str = "chunks_active"
    min_score: float = 0.0


@dataclass(frozen=True)
class VectorUpsertInput:
    chunk_id: str
    document_id: str
    content_hash: str
    embedding_model: str


@dataclass(frozen=True)
class VectorUpsertResult:
    chunk_id: str
    vector_ref: str
    status: str = "upserted"


@dataclass(frozen=True)
class VectorHit:
    document_id: str
    knowledge_source_id: str
    title: str
    confidentiality_level: str
    access_groups: tuple[str, ...]
    score: float
    citation: str
    acl_decision: str = "allow"
    rank_original: int = 0
    chunk_id: str | None = None
    citation_locator: str | None = None
    content_hash: str | None = None
    vector_ref: str | None = None


@dataclass(frozen=True)
class VectorSearchResult:
    hits: tuple[VectorHit, ...]
    denied_count: int


class VectorStore(Protocol):
    def upsert_chunks(self, chunks: Sequence[VectorUpsertInput]) -> tuple[VectorUpsertResult, ...]:
        ...

    def search(
        self,
        *,
        query: VectorQuery,
        documents: Sequence[Document],
        acl_filter: AclFilter,
    ) -> VectorSearchResult:
        ...

    def delete_document(self, document_id: str) -> None:
        ...


class FakeVectorStore:
    """Deterministic lexical adapter used until a real vector backend is wired."""

    def __init__(self) -> None:
        self._deleted_document_ids: set[str] = set()

    def upsert_chunks(self, chunks: Sequence[VectorUpsertInput]) -> tuple[VectorUpsertResult, ...]:
        return tuple(
            VectorUpsertResult(
                chunk_id=chunk.chunk_id,
                vector_ref=f"fake-vector:{chunk.embedding_model}:{chunk.chunk_id}",
            )
            for chunk in chunks
        )

    def search(
        self,
        *,
        query: VectorQuery,
        documents: Sequence[Document],
        acl_filter: AclFilter,
    ) -> VectorSearchResult:
        candidate_documents = [
            document
            for document in documents
            if document.id not in self._deleted_document_ids
            if not query.knowledge_source_ids
            or document.knowledge_source_id in query.knowledge_source_ids
        ]
        allowed_documents = [
            document
            for document in candidate_documents
            if principal_can_access_document(acl_filter.principal, document)
        ]
        denied_count = len(candidate_documents) - len(allowed_documents)

        hits: list[VectorHit] = []
        for document in allowed_documents:
            chunks = [chunk for chunk in document.chunks if chunk.status == "indexed"]
            if chunks:
                hits.extend(_chunk_hits(query.query_text, document, chunks))
                continue

            hits.append(_document_fallback_hit(query.query_text, document))

        hits.sort(key=lambda hit: (-hit.score, hit.title, hit.chunk_id or ""))
        filtered_hits = tuple(hit for hit in hits if hit.score >= query.min_score)
        return VectorSearchResult(hits=filtered_hits[: query.top_k], denied_count=denied_count)

    def delete_document(self, document_id: str) -> None:
        self._deleted_document_ids.add(document_id)


def build_acl_filter(principal: Principal) -> AclFilter:
    return AclFilter(
        principal=principal,
        subjects=tuple(sorted(principal_acl_subjects(principal))),
        clearance_level=principal.clearance_level,
    )


def _chunk_hits(query: str, document: Document, chunks: Sequence) -> list[VectorHit]:
    return [
        VectorHit(
            document_id=document.id,
            knowledge_source_id=document.knowledge_source_id,
            chunk_id=chunk.id,
            title=document.title,
            confidentiality_level=document.confidentiality_level,
            access_groups=tuple(document.access_groups),
            score=_lexical_score(query, document.title, chunk.content),
            citation=chunk.citation_locator,
            rank_original=chunk.chunk_index,
            citation_locator=chunk.citation_locator,
            content_hash=chunk.content_hash,
            vector_ref=chunk.vector_ref,
        )
        for chunk in chunks
    ]


def _document_fallback_hit(query: str, document: Document) -> VectorHit:
    return VectorHit(
        document_id=document.id,
        knowledge_source_id=document.knowledge_source_id,
        title=document.title,
        confidentiality_level=document.confidentiality_level,
        access_groups=tuple(document.access_groups),
        score=_lexical_score(query, document.title),
        citation=f"{document.title} ({document.effective_date or 'undated'})",
    )


def _lexical_score(query: str, *values: str) -> float:
    query_terms = {term.casefold() for term in query.split() if term.strip()}
    haystack_terms = {
        term.casefold()
        for value in values
        for term in value.split()
        if term.strip()
    }
    if not query_terms:
        return 0.0
    overlap = len(query_terms.intersection(haystack_terms))
    return round(overlap / len(query_terms), 4)
