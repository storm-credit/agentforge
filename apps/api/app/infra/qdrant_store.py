from __future__ import annotations

import logging
import uuid
from collections.abc import Callable, Sequence

from qdrant_client import models as qm

from app.domain.acl import confidentiality_rank
from app.domain.vector import (
    AclFilter,
    VectorHit,
    VectorQuery,
    VectorSearchResult,
    VectorUpsertInput,
    VectorUpsertResult,
)

logger = logging.getLogger(__name__)

# Only fully-indexed documents are surfaced via vector search.
# This is intentionally stricter than SEARCHABLE_DOCUMENT_STATUSES (which also
# includes "registered" and "ready") because the Qdrant filter encodes the
# "indexed" gate — payload_allows mirrors the filter, not the broader domain ACL.
_VECTOR_SEARCH_STATUSES: frozenset[str] = frozenset({"indexed"})


def build_qdrant_acl_filter(acl: AclFilter, knowledge_source_ids: tuple[str, ...]) -> qm.Filter:
    """Build a Qdrant payload filter that enforces the principal's ACL.

    Conditions (all must hold):
    - status == "indexed"
    - confidentiality_rank <= principal's clearance rank
    - access_groups intersects principal's subjects
    - knowledge_source_id in knowledge_source_ids (when supplied)
    """
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
    """Defense-in-depth re-check on a raw Qdrant payload point.

    Mirrors the semantics of build_qdrant_acl_filter (not the broader
    principal_can_access_document) so that any point that slips through
    the filter (e.g. due to a stale index) is still denied.
    """
    # Status must be "indexed" — the vector index gate.
    if payload.get("status") not in _VECTOR_SEARCH_STATUSES:
        return False

    level_rank = int(payload.get("confidentiality_rank", confidentiality_rank("confidential")))

    # Exclude confidential-and-above levels regardless of clearance.
    if level_rank >= confidentiality_rank("confidential"):
        return False

    # Principal's clearance must meet or exceed the document's rank.
    if level_rank > confidentiality_rank(acl.clearance_level):
        return False

    # Deny-by-default: empty access_groups means no one can read it.
    groups = payload.get("access_groups") or []
    if not groups:
        return False

    return bool(set(groups).intersection(acl.subjects))


def _point_id(chunk_id: str) -> str:
    """Convert an arbitrary chunk_id string to a deterministic UUID5 for Qdrant."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


class QdrantVectorStore:
    """Real vector store over Qdrant. ACL applied as an in-query payload filter."""

    def __init__(
        self,
        *,
        client,
        embed: Callable[[list[str]], list[list[float]]],
        dim: int,
        collection: str = "chunks_active",
    ) -> None:
        self._client = client
        self._embed = embed
        self._dim = dim
        self._collection = collection

    def _ensure_collection(self) -> None:
        if self._client.collection_exists(self._collection):
            return
        self._client.create_collection(
            collection_name=self._collection,
            vectors_config=qm.VectorParams(size=self._dim, distance=qm.Distance.COSINE),
        )

    def upsert_chunks(self, chunks: Sequence[VectorUpsertInput]) -> tuple[VectorUpsertResult, ...]:
        chunks = tuple(chunks)
        if not chunks:
            return ()
        self._ensure_collection()
        texts = [
            f"{c.title}\n{' / '.join(c.section_path)}\n{c.content}".strip()
            for c in chunks
        ]
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
            VectorUpsertResult(
                chunk_id=c.chunk_id,
                vector_ref=f"qdrant:{self._collection}:{c.chunk_id}",
            )
            for c in chunks
        )

    def search(
        self,
        *,
        query: VectorQuery,
        documents,
        acl_filter: AclFilter,
    ) -> VectorSearchResult:
        if not self._client.collection_exists(self._collection):
            return VectorSearchResult(hits=(), denied_count=0)
        query_vector = self._embed([query.query_text])[0]
        acl_q = build_qdrant_acl_filter(acl_filter, query.knowledge_source_ids)
        found = self._client.query_points(
            collection_name=self._collection,
            query=query_vector,
            query_filter=acl_q,
            limit=query.top_k,
            with_payload=True,
        ).points
        hits: list[VectorHit] = []
        for rank, point in enumerate(found, start=1):
            payload = point.payload or {}
            if not payload_allows(payload, acl_filter):
                logger.warning(
                    "dropping ACL-violating hit chunk_id=%s", payload.get("chunk_id")
                )
                continue
            if float(point.score) < query.min_score:
                # relevance gating: below-threshold hits are not relevant context
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
        denied_count = self._denied_count(query, allowed=len(hits))
        return VectorSearchResult(hits=tuple(hits), denied_count=denied_count)

    def _denied_count(self, query: VectorQuery, allowed: int) -> int:
        must = [
            qm.FieldCondition(key="status", match=qm.MatchValue(value="indexed"))
        ]
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
        except Exception:  # noqa: BLE001 — count is a best-effort audit signal
            return 0
        return max(0, total - allowed)

    def delete_document(self, document_id: str) -> None:
        if not self._client.collection_exists(self._collection):
            return
        self._client.delete(
            collection_name=self._collection,
            points_selector=qm.FilterSelector(
                filter=qm.Filter(
                    must=[
                        qm.FieldCondition(
                            key="document_id",
                            match=qm.MatchValue(value=document_id),
                        )
                    ]
                )
            ),
        )

    def set_document_acl(
        self, document_id: str, *, access_groups: tuple[str, ...], confidentiality_rank: int
    ) -> int:
        """Update the ACL payload fields for every chunk of a document.

        ACL is enforced as an in-query payload filter, so a payload update takes
        effect on the next search with no re-embedding. Returns the number of
        affected points.
        """
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
            points=selector,
        )
        return affected
