from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import hashlib
import json
import math
import re
from typing import TYPE_CHECKING, Protocol
from urllib import error, request
from uuid import NAMESPACE_URL, uuid5

from app.core.principal import Principal
from app.domain.acl import (
    confidentiality_rank,
    principal_acl_subjects,
    principal_can_access_document,
)

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
    min_score: float = 0.25


@dataclass(frozen=True)
class VectorUpsertInput:
    chunk_id: str
    document_id: str
    content_hash: str
    embedding_model: str
    content: str = ""
    title: str = ""
    knowledge_source_id: str = ""
    confidentiality_level: str = "internal"
    access_groups: tuple[str, ...] = ()
    citation_locator: str | None = None


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
    adapter_name: str = "fake"


class VectorStoreUnavailable(RuntimeError):
    """Raised when a configured vector backend cannot satisfy the request."""


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

        hits = _document_hits(query.query_text, allowed_documents)

        hits.sort(key=lambda hit: (-hit.score, hit.title, hit.chunk_id or ""))
        filtered_hits = tuple(hit for hit in hits if hit.score >= query.min_score)
        return VectorSearchResult(
            hits=filtered_hits[: query.top_k],
            denied_count=denied_count,
            adapter_name="fake",
        )

    def delete_document(self, document_id: str) -> None:
        self._deleted_document_ids.add(document_id)


def build_acl_filter(principal: Principal) -> AclFilter:
    return AclFilter(
        principal=principal,
        subjects=tuple(sorted(principal_acl_subjects(principal))),
        clearance_level=principal.clearance_level,
    )


class QdrantVectorStore:
    """Qdrant-backed vector adapter with ACL filters pushed into the vector query."""

    adapter_name = "qdrant"

    def __init__(
        self,
        *,
        url: str,
        collection: str,
        vector_size: int = 64,
        timeout_seconds: float = 2.0,
    ) -> None:
        self.url = url.rstrip("/")
        self.collection = collection
        self.vector_size = vector_size
        self.timeout_seconds = timeout_seconds

    def upsert_chunks(self, chunks: Sequence[VectorUpsertInput]) -> tuple[VectorUpsertResult, ...]:
        if not chunks:
            return ()

        self._ensure_collection()
        points = []
        results = []
        for chunk in chunks:
            point_id = _point_id(chunk.chunk_id)
            points.append(
                {
                    "id": point_id,
                    "vector": _embedding_vector(
                        " ".join(
                            value
                            for value in (chunk.title, chunk.content, chunk.content_hash)
                            if value
                        ),
                        self.vector_size,
                    ),
                    "payload": {
                        "chunk_id": chunk.chunk_id,
                        "document_id": chunk.document_id,
                        "knowledge_source_id": chunk.knowledge_source_id,
                        "title": chunk.title,
                        "content_hash": chunk.content_hash,
                        "embedding_model": chunk.embedding_model,
                        "confidentiality_level": chunk.confidentiality_level,
                        "confidentiality_rank": confidentiality_rank(chunk.confidentiality_level),
                        "access_groups": list(chunk.access_groups),
                        "citation_locator": chunk.citation_locator,
                        "status": "indexed",
                    },
                }
            )
            results.append(
                VectorUpsertResult(
                    chunk_id=chunk.chunk_id,
                    vector_ref=f"qdrant:{self.collection}:{point_id}",
                )
            )

        self._request(
            "PUT",
            f"/collections/{self.collection}/points?wait=true",
            {"points": points},
        )
        return tuple(results)

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
            if not query.knowledge_source_ids
            or document.knowledge_source_id in query.knowledge_source_ids
        ]
        allowed_documents = [
            document
            for document in candidate_documents
            if principal_can_access_document(acl_filter.principal, document)
        ]
        denied_count = len(candidate_documents) - len(allowed_documents)

        response_payload = self._request(
            "POST",
            f"/collections/{self.collection}/points/search",
            {
                "vector": _embedding_vector(query.query_text, self.vector_size),
                "limit": query.top_k,
                "with_payload": True,
                "score_threshold": query.min_score,
                "filter": _qdrant_acl_filter(query, acl_filter),
            },
        )
        hits = tuple(
            hit
            for hit in (_qdrant_hit(item) for item in response_payload.get("result", []))
            if hit is not None
        )
        return VectorSearchResult(
            hits=hits,
            denied_count=denied_count,
            adapter_name=self.adapter_name,
        )

    def delete_document(self, document_id: str) -> None:
        self._request(
            "POST",
            f"/collections/{self.collection}/points/delete?wait=true",
            {
                "filter": {
                    "must": [
                        {"key": "document_id", "match": {"value": document_id}},
                    ],
                },
            },
        )

    def _ensure_collection(self) -> None:
        try:
            self._request("GET", f"/collections/{self.collection}")
        except VectorStoreUnavailable as exc:
            if exc.__cause__ is not None and not isinstance(exc.__cause__, error.HTTPError):
                raise
            cause = exc.__cause__
            if not isinstance(cause, error.HTTPError) or cause.code != 404:
                raise
            self._request(
                "PUT",
                f"/collections/{self.collection}",
                {
                    "vectors": {
                        "size": self.vector_size,
                        "distance": "Cosine",
                    },
                },
            )

    def _request(
        self,
        method: str,
        path: str,
        payload: dict | None = None,
    ) -> dict:
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = request.Request(
            f"{self.url}{path}",
            data=body,
            method=method,
            headers={"Content-Type": "application/json"} if payload is not None else {},
        )

        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                content = response.read()
        except error.URLError as exc:
            raise VectorStoreUnavailable(f"Qdrant request failed: {exc}") from exc

        if not content:
            return {}
        return json.loads(content.decode("utf-8"))


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


def _document_hits(query: str, documents: Sequence[Document]) -> list[VectorHit]:
    hits: list[VectorHit] = []
    for document in documents:
        chunks = [chunk for chunk in document.chunks if chunk.status == "indexed"]
        if chunks:
            hits.extend(_chunk_hits(query, document, chunks))
            continue

        hits.append(_document_fallback_hit(query, document))
    return hits


def _qdrant_acl_filter(query: VectorQuery, acl_filter: AclFilter) -> dict:
    must: list[dict] = [
        {"key": "status", "match": {"value": "indexed"}},
        {
            "key": "confidentiality_rank",
            "range": {"lte": confidentiality_rank(acl_filter.clearance_level)},
        },
        {"key": "access_groups", "match": {"any": list(acl_filter.subjects)}},
    ]
    if query.knowledge_source_ids:
        must.append(
            {
                "key": "knowledge_source_id",
                "match": {"any": list(query.knowledge_source_ids)},
            }
        )
    return {"must": must}


def _qdrant_hit(item: object) -> VectorHit | None:
    if not isinstance(item, dict):
        return None

    payload = item.get("payload")
    if not isinstance(payload, dict):
        return None

    document_id = _string_payload(payload, "document_id")
    knowledge_source_id = _string_payload(payload, "knowledge_source_id")
    title = _string_payload(payload, "title")
    if not document_id or not knowledge_source_id or not title:
        return None

    citation_locator = _optional_string_payload(payload, "citation_locator")
    chunk_id = _optional_string_payload(payload, "chunk_id")
    return VectorHit(
        document_id=document_id,
        knowledge_source_id=knowledge_source_id,
        chunk_id=chunk_id,
        title=title,
        confidentiality_level=_string_payload(payload, "confidentiality_level") or "internal",
        access_groups=tuple(_string_list_payload(payload, "access_groups")),
        score=_number_payload(item, "score"),
        citation=citation_locator or title,
        citation_locator=citation_locator,
        content_hash=_optional_string_payload(payload, "content_hash"),
        vector_ref=f"qdrant:{_optional_string_payload(payload, 'chunk_id') or document_id}",
        rank_original=0,
    )


def _embedding_vector(text: str, dimensions: int) -> list[float]:
    vector = [0.0] * dimensions
    for token in _token_set(text):
        bucket = int(hashlib.sha256(token.encode("utf-8")).hexdigest()[:8], 16) % dimensions
        vector[bucket] += 1.0

    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude == 0:
        return vector

    return [round(value / magnitude, 6) for value in vector]


def _point_id(chunk_id: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"agentforge:chunk:{chunk_id}"))


def _string_payload(payload: dict, key: str) -> str:
    value = payload.get(key)
    return value if isinstance(value, str) else ""


def _optional_string_payload(payload: dict, key: str) -> str | None:
    value = payload.get(key)
    return value if isinstance(value, str) else None


def _string_list_payload(payload: dict, key: str) -> list[str]:
    value = payload.get(key)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _number_payload(payload: dict, key: str) -> float:
    value = payload.get(key)
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


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
    query_terms = _token_set(query)
    haystack_terms = {
        token
        for value in values
        for token in _token_set(value)
    }
    if not query_terms:
        return 0.0
    overlap = len(query_terms.intersection(haystack_terms))
    return round(overlap / len(query_terms), 4)


def _token_set(value: str) -> set[str]:
    stop_words = {
        "a",
        "after",
        "all",
        "an",
        "and",
        "are",
        "as",
        "be",
        "before",
        "can",
        "cannot",
        "does",
        "for",
        "from",
        "how",
        "i",
        "if",
        "in",
        "is",
        "it",
        "me",
        "my",
        "of",
        "or",
        "should",
        "the",
        "to",
        "what",
        "when",
        "which",
        "with",
        "you",
    }
    return {
        token
        for token in re.findall(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)?", value.casefold())
        if token not in stop_words
    }
