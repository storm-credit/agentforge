from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


REQUIRED_CITATION_FIELDS = ("document_id", "chunk_id", "title", "citation_locator")


@dataclass(frozen=True)
class CitationValidationResult:
    passed: bool
    required: bool
    citation_count: int
    error_code: str | None = None
    error_message: str | None = None
    missing_fields: tuple[str, ...] = ()


def validate_run_citations(
    citations: Sequence[Mapping[str, Any]],
    *,
    citation_required: bool,
) -> CitationValidationResult:
    if not citation_required:
        return CitationValidationResult(
            passed=True,
            required=False,
            citation_count=len(citations),
        )

    if not citations:
        return CitationValidationResult(
            passed=False,
            required=True,
            citation_count=0,
            error_code="NO_CITATION",
            error_message="Citation-required response did not include usable citations.",
        )

    missing_fields = tuple(
        sorted(
            {
                field
                for citation in citations
                for field in REQUIRED_CITATION_FIELDS
                if not citation.get(field)
            }
        )
    )
    if missing_fields:
        return CitationValidationResult(
            passed=False,
            required=True,
            citation_count=len(citations),
            error_code="BAD_CITATION",
            error_message="Citation metadata is incomplete.",
            missing_fields=missing_fields,
        )

    return CitationValidationResult(
        passed=True,
        required=True,
        citation_count=len(citations),
    )
