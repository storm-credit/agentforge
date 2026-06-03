from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.principal import Principal, get_principal
from app.domain.indexing import run_index_job
from app.domain.models import Document, DocumentChunk, IndexJob, KnowledgeSource
from app.domain.vector import FakeVectorStore, VectorQuery, build_acl_filter
from app.domain.schemas import (
    DocumentCreate,
    DocumentChunkRead,
    DocumentRead,
    IndexJobCreate,
    IndexJobProcess,
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
        run_index_job(
            db=db,
            document=document,
            job=job,
            source_text=payload.source_text,
            principal=principal,
        )

    db.commit()
    db.refresh(job)
    return job


@router.post("/index-jobs/{job_id}/process", response_model=IndexJobRead)
def process_index_job(
    job_id: str,
    payload: IndexJobProcess,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> IndexJob:
    """Worker stub: drive a queued index job through the pipeline.

    Real deployments will fetch the document body from object storage (AF-009).
    Until then a queued job is processed with the synthetic ``source_text`` provided
    here; if no content is available the job fails closed.
    """
    job = db.get(IndexJob, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Index job not found")
    if job.status != "queued":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Index job is not queued"
        )

    document = db.get(Document, job.document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if payload.source_text is None:
        job.started_at = datetime.now(UTC)
        job.status = "failed"
        job.stage = "parse"
        job.error_code = "SOURCE_CONTENT_UNAVAILABLE"
        job.error_message = (
            "No document content is available to index. Object storage retrieval is not yet wired."
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
    else:
        run_index_job(
            db=db,
            document=document,
            job=job,
            source_text=payload.source_text,
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
    statement = (
        select(Document)
        .options(selectinload(Document.chunks))
        .order_by(Document.created_at.desc())
    )
    documents = list(db.scalars(statement))
    vector_result = FakeVectorStore().search(
        query=VectorQuery(
            query_text=payload.query,
            knowledge_source_ids=tuple(payload.knowledge_source_ids),
            top_k=payload.top_k,
        ),
        documents=documents,
        acl_filter=build_acl_filter(principal),
    )
    hits = [
        RetrievalPreviewHit(
            document_id=hit.document_id,
            knowledge_source_id=hit.knowledge_source_id,
            chunk_id=hit.chunk_id,
            title=hit.title,
            confidentiality_level=hit.confidentiality_level,
            access_groups=list(hit.access_groups),
            score=hit.score,
            citation=hit.citation,
            citation_locator=hit.citation_locator,
        )
        for hit in vector_result.hits
    ]

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
            "denied_count": vector_result.denied_count,
            "vector_adapter": "fake",
        },
    )
    db.commit()

    return RetrievalPreviewResponse(
        query=payload.query,
        hits=hits,
        denied_count=vector_result.denied_count,
    )


def _index_job_config(payload: IndexJobCreate) -> dict:
    return {
        "parser_profile": payload.parser_profile,
        "chunking": payload.chunking,
        "embedding_model": payload.embedding_model,
        "force_reindex": payload.force_reindex,
        "source": "synthetic_text" if payload.source_text is not None else "object_store",
    }
