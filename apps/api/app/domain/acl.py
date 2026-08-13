from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.principal import Principal

if TYPE_CHECKING:
    from app.domain.models import Document


CONFIDENTIALITY_RANK = {
    "public": 0,
    "internal": 1,
    "restricted": 2,
    "confidential": 3,
}

SEARCHABLE_DOCUMENT_STATUSES = {"registered", "indexed", "ready"}
EXCLUDED_INDEX_CONFIDENTIALITY_LEVELS = {"confidential"}

# The fail-closed direction differs by side of the comparison: an unknown OBJECT level
# must read as the highest rank, an unknown SUBJECT clearance as the lowest.
LOWEST_CONFIDENTIALITY_RANK = min(CONFIDENTIALITY_RANK.values())


def confidentiality_rank(level: str) -> int:
    """OBJECT-side resolution: rank of a document/source confidentiality level.

    Fails closed by resolving an unrecognised level to the HIGHEST rank, so an
    unclassified object is treated as maximally sensitive. Object levels are
    validated on write by ``_validate_confidentiality`` (api/v1/knowledge.py).

    Never apply this to a principal's clearance: on the subject side the same
    default inverts into maximum clearance. Use ``principal_clearance_rank``.
    """
    return CONFIDENTIALITY_RANK.get(level.lower(), CONFIDENTIALITY_RANK["confidential"])


def principal_clearance_rank(clearance_level: str | None) -> int:
    """SUBJECT-side resolution: rank of a principal's clearance claim.

    Fails closed by resolving an unrecognised, empty, or whitespace-only value to
    the LOWEST rank, so a malformed identity claim can never widen access. The
    value is subject-supplied (``X-Agent-Forge-Clearance`` today, an IdP claim
    under ADR-103) and is not validated anywhere upstream, so surrounding
    whitespace and case are normalised first: a well-formed clearance keeps its
    exact rank regardless of padding or casing.
    """
    normalized = (clearance_level or "").strip().lower()
    return CONFIDENTIALITY_RANK.get(normalized, LOWEST_CONFIDENTIALITY_RANK)


def principal_acl_subjects(principal: Principal) -> set[str]:
    subjects = {
        "all-employees",
        f"user:{principal.user_id}",
        f"department:{principal.department}",
    }
    subjects.update(principal.groups)
    subjects.update(f"role:{role}" for role in principal.roles)
    return subjects


def principal_can_access_document(principal: Principal, document: Document) -> bool:
    if document.status not in SEARCHABLE_DOCUMENT_STATUSES:
        return False

    if document.confidentiality_level in EXCLUDED_INDEX_CONFIDENTIALITY_LEVELS:
        return False

    if principal_clearance_rank(principal.clearance_level) < confidentiality_rank(
        document.confidentiality_level
    ):
        return False

    if not document.access_groups:
        return False

    return bool(principal_acl_subjects(principal).intersection(document.access_groups))


def document_can_be_indexed(document: Document) -> bool:
    if document.status not in SEARCHABLE_DOCUMENT_STATUSES:
        return False

    if document.confidentiality_level in EXCLUDED_INDEX_CONFIDENTIALITY_LEVELS:
        return False

    return bool(document.access_groups)
