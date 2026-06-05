from __future__ import annotations

import logging

from qdrant_client import models as qm

from app.domain.acl import confidentiality_rank
from app.domain.vector import AclFilter

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
