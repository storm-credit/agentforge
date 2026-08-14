"""What one index attempt actually produced -- counted, never judged.

WO-2026-08-14-INGESTION-INSTRUMENTATION-001 (OBS-001, OBS-002).

WHY THIS EXISTS

``chunker_mime_type_for`` maps PDF and DOCX to ``text/plain``, so ``parse_txt_md_document``'s
heading detector never runs on them, ``section_path`` stays empty, and every citation becomes
``"{title} / body / lines N-M"`` -- line numbers into an extracted text STREAM, which point at
nothing a reader can open in the original file. The same document also collapses into far
fewer chunks, because chunk boundaries are heading boundaries: three separately retrievable
clauses become one blob. Both effects are invisible today. An administrator sees "indexed,
N chunks" whether the conversion preserved the clause hierarchy or destroyed it.

WHAT IS RECORDED, AND WHAT IS DELIBERATELY NOT

Every field below is something the pipeline OBSERVED: which library ran, what MIME type the
chunker was handed, how many chunks came out, how many of them carried a non-empty
``section_path``, how many characters were extracted, how many pages/paragraphs/lines the
extractor saw. There is no score, no grade, and no "quality" field. A derived judgement
presented as a measurement would reproduce the exact failure this Work Order exists to expose
-- a system reporting success it never verified.

The three warning codes are the one place a threshold is applied, and each is a restatement of
the counts next to it rather than an opinion:

``HEADING_DETECTION_UNAVAILABLE``
    The chunker was handed a MIME type whose heading detector does not run at all. Structure
    could not have survived regardless of what the source file contained. This is the §1-1
    seam, made queryable.

``NO_HEADINGS_DETECTED``
    Chunks were produced and NONE carried a section path, i.e. every citation from this
    document is ``"/ body / lines N-M"``. Follows from ``structured_chunk_count == 0``; kept
    as a code so the condition is greppable in one column alongside the others.

``LOW_TEXT_DENSITY``
    Only ever raised for page-counted formats: fewer than ``MIN_CHARS_PER_PAGE`` characters
    per page. This is the partially-scanned-PDF signal -- a cover page with a text layer makes
    extraction non-empty, so the document indexes SUCCESSFULLY while its actual policy text is
    unreachable. The threshold is a flag for a human, not a verdict: the raw
    ``extracted_char_count`` and ``source_unit_count`` are both stored, so anyone can disagree
    with the constant and recompute.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.parsers import UNIT_PAGE, ExtractedDocument, ParsedChunk

#: An attempt whose extraction and chunking this instrumentation OBSERVED to completion.
EXTRACTION_OK = "ok"
#: An attempt this instrumentation observed FAIL. Whatever counts are present were still
#: observed; the failure's error code lives on the index_jobs row this lineage row points at.
EXTRACTION_FAILED = "failed"
#: NOT OBSERVED. The only value the backfill may write for a document indexed before this
#: instrumentation existed -- see alembic/versions/0007_document_ingestions.py.
EXTRACTION_UNKNOWN = "unknown"

WARNING_HEADING_DETECTION_UNAVAILABLE = "HEADING_DETECTION_UNAVAILABLE"
WARNING_NO_HEADINGS_DETECTED = "NO_HEADINGS_DETECTED"
WARNING_LOW_TEXT_DENSITY = "LOW_TEXT_DENSITY"

#: The MIME types for which ``parse_txt_md_document`` runs its heading detector. Deliberately
#: duplicated from the parser's own ``is_markdown`` test rather than imported, so this module
#: cannot silently change parsing; ``test_ingestion_lineage`` cross-checks the two sets
#: BEHAVIOURALLY (it parses a heading with each supported MIME type and compares).
HEADING_AWARE_MIME_TYPES = frozenset({"text/markdown", "text/x-markdown"})

#: Below this many characters per page, a page-counted document is flagged for human review.
#: Rationale for the value: an A4 page of Korean policy text runs to several hundred
#: characters; a title-only or image-only page yields tens. 200 sits between those, and a
#: document only reaches this code path if extraction produced SOME text (an empty extraction
#: already fails with EMPTY_EXTRACTED_TEXT). Adjusting it changes only which rows carry a
#: warning -- never what is indexed, never what is retrievable.
MIN_CHARS_PER_PAGE = 200


@dataclass(frozen=True)
class IngestionLineage:
    """The observation record for one index attempt. ``None`` means NOT OBSERVED, never zero."""

    extraction_status: str
    source_mime_type: str
    converted_mime_type: str | None = None
    converter_chain: str | None = None
    chunk_count: int | None = None
    structured_chunk_count: int | None = None
    extracted_char_count: int | None = None
    source_unit_kind: str | None = None
    source_unit_count: int | None = None
    warnings: tuple[str, ...] = ()


def build_lineage(
    *,
    extraction_status: str,
    source_mime_type: str,
    converted_mime_type: str | None = None,
    extraction: ExtractedDocument | None = None,
    chunks: Sequence[ParsedChunk] | None = None,
) -> IngestionLineage:
    """Count what this attempt produced.

    Every argument is optional except the status and the declared MIME type, because an
    attempt can fail before conversion (document not indexable), after conversion but before
    chunking (unsupported chunker MIME type), or after both (empty chunk set). Whatever was
    observed by the time it failed is still recorded; the rest stays ``None``.
    """
    chunk_count = None if chunks is None else len(chunks)
    structured_chunk_count = (
        None if chunks is None else sum(1 for chunk in chunks if chunk.section_path)
    )
    extracted_char_count = None if extraction is None else len(extraction.text)
    return IngestionLineage(
        extraction_status=extraction_status,
        source_mime_type=source_mime_type,
        converted_mime_type=converted_mime_type,
        converter_chain=_converter_chain(extraction, converted_mime_type),
        chunk_count=chunk_count,
        structured_chunk_count=structured_chunk_count,
        extracted_char_count=extracted_char_count,
        source_unit_kind=None if extraction is None else extraction.source_unit_kind,
        source_unit_count=None if extraction is None else extraction.source_unit_count,
        warnings=_warnings(
            converted_mime_type=converted_mime_type,
            extraction=extraction,
            chunk_count=chunk_count,
            structured_chunk_count=structured_chunk_count,
        ),
    )


def _converter_chain(
    extraction: ExtractedDocument | None, converted_mime_type: str | None
) -> str | None:
    """``pypdf/6.14.2>text/plain`` -- what ran, at which version, and what the chunker got."""
    if extraction is None:
        return None
    return f"{extraction.converter}>{converted_mime_type or 'unknown'}"


def _warnings(
    *,
    converted_mime_type: str | None,
    extraction: ExtractedDocument | None,
    chunk_count: int | None,
    structured_chunk_count: int | None,
) -> tuple[str, ...]:
    warnings: list[str] = []
    if converted_mime_type is not None and converted_mime_type not in HEADING_AWARE_MIME_TYPES:
        warnings.append(WARNING_HEADING_DETECTION_UNAVAILABLE)
    if chunk_count and not structured_chunk_count:
        warnings.append(WARNING_NO_HEADINGS_DETECTED)
    if is_low_text_density(extraction):
        warnings.append(WARNING_LOW_TEXT_DENSITY)
    return tuple(warnings)


def is_low_text_density(extraction: ExtractedDocument | None) -> bool:
    """Page-counted formats only -- see ``MIN_CHARS_PER_PAGE`` and ``UNIT_PAGE``."""
    if extraction is None or extraction.source_unit_kind != UNIT_PAGE:
        return False
    if extraction.source_unit_count <= 0:
        return False
    return len(extraction.text) / extraction.source_unit_count < MIN_CHARS_PER_PAGE
