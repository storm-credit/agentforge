"""Index job worker.

Runs the deterministic parse -> chunk -> upsert pipeline for an index job and
records the job state transitions (running -> succeeded/failed). The worker reads
its parameters from ``job.config`` so it can drive both the synchronous create path
and the queued/process path with the same logic.
"""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.principal import Principal
from app.domain.acl import confidentiality_rank, document_can_be_indexed
from app.domain.models import Document, DocumentChunk, IndexJob
from app.domain.parsers import (
    SUPPORTED_BINARY_MIME_TYPES,
    DocumentExtractionError,
    chunker_mime_type_for,
    extract_text_from_bytes,
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
        job.status = "failed"
        job.error_code = "DOCUMENT_NOT_INDEXABLE"
        job.error_message = (
            "Document is missing ACL metadata, is not searchable, or is excluded by confidentiality."
        )
        job.finished_at = datetime.now(UTC)
        document.status = "index_failed"
        write_audit_event(
            db,
            principal=principal,
            event_type="document.index_failed",
            target_type="document",
            target_id=document.id,
            payload={"index_job_id": job.id, "error_code": job.error_code},
        )
        return

    try:
        text_for_chunking = _source_text_for_index(
            document=document,
            source_text=source_text,
            source_bytes=source_bytes,
        )
        parsed_chunks = parse_txt_md_document(
            document_id=document.id,
            document_version=document.effective_date or "v0",
            title=document.title,
            mime_type=chunker_mime_type_for(document.mime_type),
            source_text=text_for_chunking,
            target_tokens=target_tokens,
            overlap_tokens=overlap_tokens,
        )
    except DocumentExtractionError as exc:
        job.status = "failed"
        job.error_code = exc.code
        job.error_message = str(exc)
        job.finished_at = datetime.now(UTC)
        document.status = "index_failed"
        write_audit_event(
            db,
            principal=principal,
            event_type="document.index_failed",
            target_type="document",
            target_id=document.id,
            payload={"index_job_id": job.id, "error_code": job.error_code},
        )
        return
    except ValueError as exc:
        job.status = "failed"
        job.error_code = "UNSUPPORTED_MIME_TYPE"
        job.error_message = str(exc)
        job.finished_at = datetime.now(UTC)
        document.status = "index_failed"
        write_audit_event(
            db,
            principal=principal,
            event_type="document.index_failed",
            target_type="document",
            target_id=document.id,
            payload={"index_job_id": job.id, "error_code": job.error_code},
        )
        return

    if not parsed_chunks:
        job.status = "failed"
        job.error_code = "EMPTY_EXTRACTED_TEXT"
        job.error_message = "Document content did not produce any indexable chunks."
        job.finished_at = datetime.now(UTC)
        document.status = "index_failed"
        write_audit_event(
            db,
            principal=principal,
            event_type="document.index_failed",
            target_type="document",
            target_id=document.id,
            payload={"index_job_id": job.id, "error_code": job.error_code},
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
        job.status = "failed"
        job.error_code = "VECTOR_UPSERT_FAILED"
        job.error_message = str(exc)
        job.finished_at = datetime.now(UTC)
        document.status = "index_failed"
        write_audit_event(
            db, principal=principal, event_type="document.index_failed",
            target_type="document", target_id=document.id,
            payload={"index_job_id": job.id, "error_code": job.error_code},
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
    write_audit_event(
        db,
        principal=principal,
        event_type="document.indexed",
        target_type="document",
        target_id=document.id,
        payload={"index_job_id": job.id, "chunk_count": job.chunk_count},
    )


def _source_text_for_index(
    *,
    document: Document,
    source_text: str | None,
    source_bytes: bytes | None,
) -> str:
    if document.mime_type in SUPPORTED_BINARY_MIME_TYPES:
        return extract_text_from_bytes(
            mime_type=document.mime_type,
            content=source_bytes or b"",
        )
    return source_text or ""
