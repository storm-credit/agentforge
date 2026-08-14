"""Index job worker.

Runs the deterministic parse -> chunk -> upsert pipeline for an index job and
records the job state transitions (running -> succeeded/failed). The worker reads
its parameters from ``job.config`` so it can drive both the synchronous create path
and the queued/process path with the same logic.

It also writes ONE append-only ``document_ingestions`` row per attempt -- success or failure
-- recording what the conversion produced (WO-2026-08-14-INGESTION-INSTRUMENTATION). That
recording is strictly an observation: this module hands the counts to
``app.domain.ingestion_lineage`` and changes nothing about conversion, chunking or the
citation locator.
"""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.principal import Principal
from app.domain.acl import confidentiality_rank, document_can_be_indexed
from app.domain.ingestion_lineage import (
    EXTRACTION_FAILED,
    EXTRACTION_OK,
    IngestionLineage,
    build_lineage,
)
from app.domain.models import Document, DocumentChunk, DocumentIngestion, IndexJob
from app.domain.parsers import (
    SUPPORTED_BINARY_MIME_TYPES,
    TEXT_IDENTITY_CONVERTER,
    UNIT_LINE,
    DocumentExtractionError,
    ExtractedDocument,
    chunker_mime_type_for,
    extract_document,
    parse_txt_md_document,
)
from app.domain.vector import VectorUpsertInput, get_vector_store
from app.infra.audit import write_audit_event


def run_index_job(
    *,
    db: Session,
    document: Document,
    job: IndexJob,
    principal: Principal,
    source_text: str | None = None,
    source_bytes: bytes | None = None,
) -> None:
    """Execute the index job pipeline and record its state transitions.

    Parameters such as chunking, embedding model, and force-reindex are read from
    ``job.config`` (populated at creation time) so the worker is independent of the
    request payload.
    """
    settings = get_settings()
    config = job.config or {}
    chunking = config.get("chunking") or {}
    embedding_model = config.get("embedding_model", "none-smoke")
    force_reindex = bool(config.get("force_reindex", False))
    target_tokens = int(chunking.get("target_tokens", settings.chunk_target_tokens))
    overlap_tokens = int(chunking.get("overlap_tokens", settings.chunk_overlap_tokens))
    overlap_tokens = max(0, min(overlap_tokens, target_tokens - 1))

    job.started_at = datetime.now(UTC)
    job.status = "running"
    job.stage = "parse"

    if not document_can_be_indexed(document):
        _fail_attempt(
            db=db,
            document=document,
            job=job,
            principal=principal,
            error_code="DOCUMENT_NOT_INDEXABLE",
            error_message=(
                "Document is missing ACL metadata, is not searchable, or is excluded by "
                "confidentiality."
            ),
            # Nothing was converted, so nothing but the declared MIME type is known. The row
            # still exists: an attempt that never reached the converter is itself a fact.
            lineage=build_lineage(
                extraction_status=EXTRACTION_FAILED, source_mime_type=document.mime_type
            ),
        )
        return

    extraction: ExtractedDocument | None = None
    converted_mime_type: str | None = None
    try:
        extraction = _extraction_for_index(
            document=document,
            source_text=source_text,
            source_bytes=source_bytes,
        )
        converted_mime_type = chunker_mime_type_for(document.mime_type)
        parsed_chunks = parse_txt_md_document(
            document_id=document.id,
            document_version=document.effective_date or "v0",
            title=document.title,
            mime_type=converted_mime_type,
            source_text=extraction.text,
            target_tokens=target_tokens,
            overlap_tokens=overlap_tokens,
        )
    except DocumentExtractionError as exc:
        _fail_attempt(
            db=db,
            document=document,
            job=job,
            principal=principal,
            error_code=exc.code,
            error_message=str(exc),
            lineage=build_lineage(
                extraction_status=EXTRACTION_FAILED,
                source_mime_type=document.mime_type,
                converted_mime_type=converted_mime_type,
                extraction=extraction,
            ),
        )
        return
    except ValueError as exc:
        _fail_attempt(
            db=db,
            document=document,
            job=job,
            principal=principal,
            error_code="UNSUPPORTED_MIME_TYPE",
            error_message=str(exc),
            lineage=build_lineage(
                extraction_status=EXTRACTION_FAILED,
                source_mime_type=document.mime_type,
                converted_mime_type=converted_mime_type,
                extraction=extraction,
            ),
        )
        return

    if not parsed_chunks:
        _fail_attempt(
            db=db,
            document=document,
            job=job,
            principal=principal,
            error_code="EMPTY_EXTRACTED_TEXT",
            error_message="Document content did not produce any indexable chunks.",
            lineage=build_lineage(
                extraction_status=EXTRACTION_FAILED,
                source_mime_type=document.mime_type,
                converted_mime_type=converted_mime_type,
                extraction=extraction,
                chunks=parsed_chunks,
            ),
        )
        return

    if force_reindex:
        for chunk in list(document.chunks):
            db.delete(chunk)
        db.flush()

    acl_snapshot = {
        "confidentiality_level": document.confidentiality_level,
        "access_groups": document.access_groups,
        "knowledge_source_id": document.knowledge_source_id,
    }
    try:
        confidentiality_rank_value = confidentiality_rank(document.confidentiality_level)
        store = get_vector_store()
        # Purge any existing vectors for this document before upserting. Chunk ids are
        # content/line-derived, so an edited re-index produces new ids and would orphan
        # the old vectors (which keep their ACL payload and stay searchable). No-op on
        # first index. Mirrors the archive purge (PR #38).
        store.delete_document(document.id)
        upsert_results = store.upsert_chunks(
            tuple(
                VectorUpsertInput(
                    chunk_id=parsed_chunk.chunk_id,
                    document_id=document.id,
                    content_hash=parsed_chunk.content_hash,
                    embedding_model=embedding_model,
                    content=parsed_chunk.content,
                    title=document.title,
                    section_path=tuple(parsed_chunk.section_path),
                    citation_locator=parsed_chunk.citation_locator,
                    access_groups=tuple(document.access_groups),
                    confidentiality_rank=confidentiality_rank_value,
                    knowledge_source_id=document.knowledge_source_id,
                )
                for parsed_chunk in parsed_chunks
            )
        )
    except Exception as exc:  # noqa: BLE001 - fail the job, never store half-indexed chunks
        _fail_attempt(
            db=db,
            document=document,
            job=job,
            principal=principal,
            error_code="VECTOR_UPSERT_FAILED",
            error_message=str(exc),
            # Conversion and chunking DID complete here; only the vector store failed. The
            # counts are real observations and are kept, which is what makes "the converter
            # was fine, the store was not" distinguishable after the fact.
            lineage=build_lineage(
                extraction_status=EXTRACTION_FAILED,
                source_mime_type=document.mime_type,
                converted_mime_type=converted_mime_type,
                extraction=extraction,
                chunks=parsed_chunks,
            ),
        )
        return
    vector_refs = {result.chunk_id: result.vector_ref for result in upsert_results}

    job.stage = "chunk"
    for parsed_chunk in parsed_chunks:
        db.add(
            DocumentChunk(
                id=parsed_chunk.chunk_id,
                document_id=document.id,
                chunk_index=parsed_chunk.chunk_index,
                content=parsed_chunk.content,
                content_hash=parsed_chunk.content_hash,
                chunk_hash=parsed_chunk.chunk_hash,
                token_count=parsed_chunk.token_count,
                line_start=parsed_chunk.line_start,
                line_end=parsed_chunk.line_end,
                section_path=list(parsed_chunk.section_path),
                citation_locator=parsed_chunk.citation_locator,
                parser_version=parsed_chunk.parser_version,
                chunker_version=parsed_chunk.chunker_version,
                embedding_model=embedding_model,
                vector_ref=vector_refs[parsed_chunk.chunk_id],
                acl_snapshot=acl_snapshot,
                status="indexed",
            )
        )

    job.status = "succeeded"
    job.stage = "upsert"
    job.chunk_count = len(parsed_chunks)
    job.artifact_uri = f"db://document_chunks/{document.id}"
    job.finished_at = datetime.now(UTC)
    document.status = "indexed"
    # Durable trust marker: once a document has successfully held indexed content it is
    # forever treated as "previously trusted" for reindex-authorization purposes. This is
    # set once here and NEVER reset (not on a later index_failed, archive, or restore), so
    # a document that drops back to 'index_failed' after its vectors are purged still
    # requires PRIVILEGED_ROLES to reindex -- closing the index_failed side door that a
    # status-only gate leaves open.
    document.has_been_indexed = True
    _record_ingestion(
        db=db,
        document=document,
        job=job,
        lineage=build_lineage(
            extraction_status=EXTRACTION_OK,
            source_mime_type=document.mime_type,
            converted_mime_type=converted_mime_type,
            extraction=extraction,
            chunks=parsed_chunks,
        ),
    )
    write_audit_event(
        db,
        principal=principal,
        event_type="document.indexed",
        target_type="document",
        target_id=document.id,
        payload={"index_job_id": job.id, "chunk_count": job.chunk_count},
    )


def _extraction_for_index(
    *,
    document: Document,
    source_text: str | None,
    source_bytes: bytes | None,
) -> ExtractedDocument:
    """The text this attempt will chunk, plus what produced it.

    The binary branch is ``extract_document``, whose ``.text`` is the identical string
    ``extract_text_from_bytes`` returned before this Work Order (it is now that function's
    implementation).

    The TXT/MD branch deliberately does NOT go through ``extract_document``: caller-supplied
    ``source_text`` has never been stripped or rejected-when-empty on this path, and routing it
    through the upload extractor would start raising ``EMPTY_EXTRACTED_TEXT`` where the code
    previously produced an empty chunk list and failed with the same code by a different route.
    Instrumentation must not change control flow, so the string is passed through untouched and
    only DESCRIBED here.
    """
    if document.mime_type in SUPPORTED_BINARY_MIME_TYPES:
        return extract_document(
            mime_type=document.mime_type,
            content=source_bytes or b"",
        )
    text = source_text or ""
    return ExtractedDocument(
        text=text,
        converter=TEXT_IDENTITY_CONVERTER,
        source_unit_kind=UNIT_LINE,
        source_unit_count=len(text.split("\n")),
    )


def _fail_attempt(
    *,
    db: Session,
    document: Document,
    job: IndexJob,
    principal: Principal,
    error_code: str,
    error_message: str,
    lineage: IngestionLineage,
) -> None:
    """Record a failed attempt exactly as before, plus its lineage row.

    Every failure branch in this module previously repeated these six statements verbatim;
    they are collected here so the lineage write cannot be forgotten in one branch. The
    statements, their order, and the audit payload are unchanged.
    """
    job.status = "failed"
    job.error_code = error_code
    job.error_message = error_message
    job.finished_at = datetime.now(UTC)
    document.status = "index_failed"
    _record_ingestion(db=db, document=document, job=job, lineage=lineage)
    write_audit_event(
        db,
        principal=principal,
        event_type="document.index_failed",
        target_type="document",
        target_id=document.id,
        payload={"index_job_id": job.id, "error_code": job.error_code},
    )


def _record_ingestion(
    *,
    db: Session,
    document: Document,
    job: IndexJob,
    lineage: IngestionLineage,
) -> None:
    """APPEND a lineage row. Never updates an existing one -- that is the whole point.

    There is no lookup-then-update here and there must never be one: a re-index adds a row so
    the population a converter defect touched stays identifiable.
    """
    db.add(
        DocumentIngestion(
            document_id=document.id,
            index_job_id=job.id,
            extraction_status=lineage.extraction_status,
            source_mime_type=lineage.source_mime_type,
            converted_mime_type=lineage.converted_mime_type,
            converter_chain=lineage.converter_chain,
            chunk_count=lineage.chunk_count,
            structured_chunk_count=lineage.structured_chunk_count,
            extracted_char_count=lineage.extracted_char_count,
            source_unit_kind=lineage.source_unit_kind,
            source_unit_count=lineage.source_unit_count,
            warnings=list(lineage.warnings),
        )
    )
