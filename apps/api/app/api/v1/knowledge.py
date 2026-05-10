from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.principal import Principal, get_principal
from app.domain.acl import document_can_be_indexed, principal_can_access_document
from app.domain.models import Document, DocumentChunk, IndexJob, KnowledgeSource
from app.domain.parsers import parse_txt_md_document
from app.domain.schemas import (
    DocumentCreate,
    DocumentChunkRead,
    DocumentRead,
    IndexJobCreate,
    IndexJobRead,
    KnowledgeSourceCreate,
    KnowledgeSourceRead,
    RetrievalPreviewHit,
    RetrievalPreviewRequest,
    RetrievalPreviewResponse,
)
from app.infra.audit import write_audit_event

router = APIRouter()


@router.get("/sources", response_model=list[KnowledgeSourceRead])
def list_sources(db: Session = Depends(get_db)) -> list[KnowledgeSource]:
    return list(db.scalars(select(KnowledgeSource).order_by(KnowledgeSource.created_at.desc())))


@router.post("/sources", response_model=KnowledgeSourceRead, status_code=status.HTTP_201_CREATED)
def create_source(
    payload: KnowledgeSourceCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> KnowledgeSource:
    source = KnowledgeSource(**payload.model_dump())
    db.add(source)
    db.flush()
    write_audit_event(
        db,
        principal=principal,
        event_type="knowledge_source.created",
        target_type="knowledge_source",
        target_id=source.id,
        payload={"name": source.name, "owner_department": source.owner_department},
    )
    db.commit()
    db.refresh(source)
    return source


@router.get("/documents", response_model=list[DocumentRead])
def list_documents(db: Session = Depends(get_db)) -> list[Document]:
    return list(db.scalars(select(Document).order_by(Document.created_at.desc())))


@router.post("/documents", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
def register_document(
    payload: DocumentCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> Document:
    source = db.get(KnowledgeSource, payload.knowledge_source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge source not found")

    document = Document(**payload.model_dump())
    db.add(document)
    db.flush()
    write_audit_event(
        db,
        principal=principal,
        event_type="document.registered",
        target_type="document",
        target_id=document.id,
        payload={
            "knowledge_source_id": document.knowledge_source_id,
            "title": document.title,
            "confidentiality_level": document.confidentiality_level,
        },
    )
    db.commit()
    db.refresh(document)
    return document


@router.post(
    "/documents/{document_id}/index-jobs",
    response_model=IndexJobRead,
    status_code=status.HTTP_201_CREATED,
)
def create_index_job(
    document_id: str,
    payload: IndexJobCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> IndexJob:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    job = IndexJob(
        document_id=document.id,
        status="queued",
        stage="parse",
        config=_index_job_config(payload),
        created_by=principal.user_id,
    )
    db.add(job)
    db.flush()

    if payload.source_text is None:
        write_audit_event(
            db,
            principal=principal,
            event_type="index_job.queued",
            target_type="index_job",
            target_id=job.id,
            payload={
                "document_id": document.id,
                "parser_profile": payload.parser_profile,
                "embedding_model": payload.embedding_model,
            },
        )
    else:
        _run_synthetic_index_job(
            db=db,
            document=document,
            job=job,
            payload=payload,
            principal=principal,
        )

    db.commit()
    db.refresh(job)
    return job


@router.get("/index-jobs/{job_id}", response_model=IndexJobRead)
def get_index_job(job_id: str, db: Session = Depends(get_db)) -> IndexJob:
    job = db.get(IndexJob, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Index job not found")
    return job


@router.get("/documents/{document_id}/chunks", response_model=list[DocumentChunkRead])
def list_document_chunks(document_id: str, db: Session = Depends(get_db)) -> list[DocumentChunk]:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    return list(
        db.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
        )
    )


@router.post("/retrieval/preview", response_model=RetrievalPreviewResponse)
def preview_retrieval(
    payload: RetrievalPreviewRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> RetrievalPreviewResponse:
    statement = select(Document).options(selectinload(Document.chunks)).order_by(Document.created_at.desc())
    if payload.knowledge_source_ids:
        statement = statement.where(Document.knowledge_source_id.in_(payload.knowledge_source_ids))

    documents = list(db.scalars(statement))
    allowed_documents = [
        document for document in documents if principal_can_access_document(principal, document)
    ]
    denied_count = len(documents) - len(allowed_documents)

    hits = _retrieval_hits(payload.query, allowed_documents)
    hits.sort(key=lambda hit: (-hit.score, hit.title))
    hits = hits[: payload.top_k]

    write_audit_event(
        db,
        principal=principal,
        event_type="retrieval.previewed",
        target_type="retrieval_preview",
        target_id="synthetic",
        payload={
            "query_length": len(payload.query),
            "knowledge_source_count": len(payload.knowledge_source_ids),
            "result_count": len(hits),
            "denied_count": denied_count,
        },
    )
    db.commit()

    return RetrievalPreviewResponse(
        query=payload.query,
        hits=hits,
        denied_count=denied_count,
    )


def _run_synthetic_index_job(
    *,
    db: Session,
    document: Document,
    job: IndexJob,
    payload: IndexJobCreate,
    principal: Principal,
) -> None:
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
        parsed_chunks = parse_txt_md_document(
            document_id=document.id,
            document_version=document.effective_date or "v0",
            title=document.title,
            mime_type=document.mime_type,
            source_text=payload.source_text or "",
            chunk_size=int(payload.chunking.get("chunk_size", 900)),
        )
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

    if payload.force_reindex:
        for chunk in list(document.chunks):
            db.delete(chunk)
        db.flush()

    acl_snapshot = {
        "confidentiality_level": document.confidentiality_level,
        "access_groups": document.access_groups,
        "knowledge_source_id": document.knowledge_source_id,
    }
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
                embedding_model=payload.embedding_model,
                vector_ref=parsed_chunk.vector_ref,
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
    write_audit_event(
        db,
        principal=principal,
        event_type="document.indexed",
        target_type="document",
        target_id=document.id,
        payload={"index_job_id": job.id, "chunk_count": job.chunk_count},
    )


def _index_job_config(payload: IndexJobCreate) -> dict:
    return {
        "parser_profile": payload.parser_profile,
        "chunking": payload.chunking,
        "embedding_model": payload.embedding_model,
        "force_reindex": payload.force_reindex,
        "source": "synthetic_text" if payload.source_text is not None else "object_store",
    }


def _retrieval_hits(query: str, allowed_documents: list[Document]) -> list[RetrievalPreviewHit]:
    hits: list[RetrievalPreviewHit] = []
    for document in allowed_documents:
        indexed_chunks = [chunk for chunk in document.chunks if chunk.status == "indexed"]
        if indexed_chunks:
            hits.extend(
                RetrievalPreviewHit(
                    document_id=document.id,
                    knowledge_source_id=document.knowledge_source_id,
                    chunk_id=chunk.id,
                    title=document.title,
                    confidentiality_level=document.confidentiality_level,
                    access_groups=document.access_groups,
                    score=_lexical_score(query, document.title, chunk.content),
                    citation=chunk.citation_locator,
                    citation_locator=chunk.citation_locator,
                )
                for chunk in indexed_chunks
            )
            continue

        hits.append(
            RetrievalPreviewHit(
                document_id=document.id,
                knowledge_source_id=document.knowledge_source_id,
                title=document.title,
                confidentiality_level=document.confidentiality_level,
                access_groups=document.access_groups,
                score=_lexical_score(query, document.title),
                citation=f"{document.title} ({document.effective_date or 'undated'})",
            )
        )
    return hits


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
