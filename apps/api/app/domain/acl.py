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


def confidentiality_rank(level: str) -> int:
    return CONFIDENTIALITY_RANK.get(level.lower(), CONFIDENTIALITY_RANK["confidential"])


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

    if confidentiality_rank(principal.clearance_level) < confidentiality_rank(
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
