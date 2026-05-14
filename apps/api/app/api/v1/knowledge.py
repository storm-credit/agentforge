import hashlib
import json
import mimetypes
import re
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.principal import Principal, get_principal
from app.domain.acl import document_can_be_indexed
from app.domain.models import Document, DocumentChunk, IndexJob, KnowledgeSource, new_id
from app.domain.parsers import SUPPORTED_TEXT_MIME_TYPES, parse_txt_md_document
from app.domain.vector import VectorQuery, VectorUpsertInput, build_acl_filter
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
from app.infra.storage import (
    ObjectStorage,
    ObjectStorageError,
    ObjectStorageNotFound,
    StorageProvider,
    get_object_storage_provider,
)
from app.infra.vector_store import get_vector_store

router = APIRouter()


@dataclass(frozen=True)
class IndexSourceError(Exception):
    error_code: str
    message: str


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


@router.post("/documents/upload", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_document(
    request: Request,
    knowledge_source_id: str = Query(min_length=1),
    title: str | None = Query(default=None, min_length=1, max_length=240),
    confidentiality_level: str | None = Query(default=None, max_length=40),
    access_groups: str = Query(default=""),
    effective_date: str | None = Query(default=None, max_length=20),
    filename: str | None = Header(default=None, alias="X-Agent-Forge-Filename"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
    storage_provider: StorageProvider = Depends(get_object_storage_provider),
) -> Document:
    source = db.get(KnowledgeSource, knowledge_source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge source not found")

    content = await request.body()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded document is empty",
        )

    document_id = new_id()
    resolved_filename = _safe_filename(filename)
    mime_type = _resolve_upload_mime_type(
        filename=resolved_filename,
        content_type=request.headers.get("content-type"),
    )
    object_key = f"knowledge/{source.id}/documents/{document_id}/{resolved_filename}"
    checksum = _sha256_bytes(content)

    try:
        stored_object = storage_provider().put_bytes(
            key=object_key,
            content=content,
            content_type=mime_type,
        )
    except ObjectStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    document = Document(
        id=document_id,
        knowledge_source_id=source.id,
        title=title.strip() if title else _title_from_filename(resolved_filename),
        object_uri=stored_object.uri,
        checksum=checksum,
        mime_type=mime_type,
        confidentiality_level=confidentiality_level or source.default_confidentiality_level,
        access_groups=_parse_access_groups(access_groups),
        status="registered",
        effective_date=effective_date,
    )
    db.add(document)
    db.flush()
    write_audit_event(
        db,
        principal=principal,
        event_type="document.uploaded",
        target_type="document",
        target_id=document.id,
        payload={
            "knowledge_source_id": source.id,
            "title": document.title,
            "filename": resolved_filename,
            "object_uri": document.object_uri,
            "checksum": document.checksum,
            "mime_type": document.mime_type,
            "size_bytes": stored_object.size_bytes,
            "confidentiality_level": document.confidentiality_level,
            "access_group_count": len(document.access_groups),
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
    storage_provider: StorageProvider = Depends(get_object_storage_provider),
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

    try:
        source_text = _index_source_text(
            document=document,
            payload=payload,
            storage_provider=storage_provider,
        )
    except IndexSourceError as exc:
        _fail_index_job(
            db=db,
            document=document,
            job=job,
            principal=principal,
            error_code=exc.error_code,
            error_message=exc.message,
        )
    else:
        _run_index_job(
            db=db,
            document=document,
            job=job,
            payload=payload,
            principal=principal,
            source_text=source_text,
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
    vector_result = get_vector_store().search(
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
            "vector_adapter": vector_result.adapter_name,
        },
    )
    db.commit()

    return RetrievalPreviewResponse(
        query=payload.query,
        hits=hits,
        denied_count=vector_result.denied_count,
    )


def _index_source_text(
    *,
    document: Document,
    payload: IndexJobCreate,
    storage_provider: StorageProvider,
) -> str:
    if payload.source_text is not None:
        return payload.source_text

    if document.mime_type not in SUPPORTED_TEXT_MIME_TYPES:
        raise IndexSourceError(
            error_code="UNSUPPORTED_MIME_TYPE",
            message=f"Unsupported text parser MIME type: {document.mime_type}",
        )

    try:
        content = _read_storage_object(storage_provider(), document.object_uri)
    except ObjectStorageNotFound as exc:
        raise IndexSourceError(
            error_code="SOURCE_OBJECT_NOT_FOUND",
            message=str(exc),
        ) from exc
    except ObjectStorageError as exc:
        raise IndexSourceError(
            error_code="SOURCE_OBJECT_READ_FAILED",
            message=str(exc),
        ) from exc

    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise IndexSourceError(
            error_code="UNSUPPORTED_TEXT_ENCODING",
            message="Stored TXT/MD document must be UTF-8 encoded.",
        ) from exc


def _read_storage_object(storage: ObjectStorage, object_uri: str) -> bytes:
    return storage.get_bytes(object_uri)


def _fail_index_job(
    *,
    db: Session,
    document: Document,
    job: IndexJob,
    principal: Principal,
    error_code: str,
    error_message: str,
) -> None:
    job.status = "failed"
    job.error_code = error_code
    job.error_message = error_message
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


def _run_index_job(
    *,
    db: Session,
    document: Document,
    job: IndexJob,
    payload: IndexJobCreate,
    principal: Principal,
    source_text: str,
) -> None:
    job.started_at = datetime.now(UTC)
    job.status = "running"
    job.stage = "parse"

    if not document_can_be_indexed(document):
        _fail_index_job(
            db=db,
            document=document,
            job=job,
            principal=principal,
            error_code="DOCUMENT_NOT_INDEXABLE",
            error_message=(
                "Document is missing ACL metadata, is not searchable, or is excluded by "
                "confidentiality."
            ),
        )
        return

    try:
        parsed_chunks = parse_txt_md_document(
            document_id=document.id,
            document_version=document.effective_date or "v0",
            title=document.title,
            mime_type=document.mime_type,
            source_text=source_text,
            chunk_size=int(payload.chunking.get("chunk_size", 900)),
        )
    except ValueError as exc:
        _fail_index_job(
            db=db,
            document=document,
            job=job,
            principal=principal,
            error_code="UNSUPPORTED_MIME_TYPE",
            error_message=str(exc),
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
    vector_store = get_vector_store()
    upsert_results = vector_store.upsert_chunks(
        tuple(
            VectorUpsertInput(
                chunk_id=parsed_chunk.chunk_id,
                document_id=document.id,
                content_hash=parsed_chunk.content_hash,
                embedding_model=payload.embedding_model,
                content=parsed_chunk.content,
                title=document.title,
                knowledge_source_id=document.knowledge_source_id,
                confidentiality_level=document.confidentiality_level,
                access_groups=tuple(document.access_groups),
                citation_locator=parsed_chunk.citation_locator,
            )
            for parsed_chunk in parsed_chunks
        )
    )
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
                embedding_model=payload.embedding_model,
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
    write_audit_event(
        db,
        principal=principal,
        event_type="document.indexed",
        target_type="document",
        target_id=document.id,
        payload={
            "index_job_id": job.id,
            "chunk_count": job.chunk_count,
            "vector_adapter": getattr(vector_store, "adapter_name", "unknown"),
        },
    )


def _index_job_config(payload: IndexJobCreate) -> dict:
    return {
        "parser_profile": payload.parser_profile,
        "chunking": payload.chunking,
        "embedding_model": payload.embedding_model,
        "force_reindex": payload.force_reindex,
        "source": "synthetic_text" if payload.source_text is not None else "object_store",
    }


def _safe_filename(filename: str | None) -> str:
    raw_name = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1] if filename else "upload.txt"
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", raw_name).strip(".-")
    return safe_name or "upload.txt"


def _title_from_filename(filename: str) -> str:
    stem = filename.rsplit(".", 1)[0].replace("-", " ").replace("_", " ").strip()
    return stem.title() if stem else "Uploaded Document"


def _resolve_upload_mime_type(*, filename: str, content_type: str | None) -> str:
    normalized_content_type = (content_type or "").split(";", 1)[0].strip().lower()
    if normalized_content_type and normalized_content_type != "application/octet-stream":
        return normalized_content_type

    lowered = filename.lower()
    if lowered.endswith(".md") or lowered.endswith(".markdown"):
        return "text/markdown"
    if lowered.endswith(".txt"):
        return "text/plain"

    guessed, _ = mimetypes.guess_type(filename)
    return guessed or normalized_content_type or "application/octet-stream"


def _parse_access_groups(access_groups: str) -> list[str]:
    raw_value = access_groups.strip()
    if not raw_value:
        return []

    if raw_value.startswith("["):
        try:
            parsed = json.loads(raw_value)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="access_groups must be JSON array or comma-separated string",
            ) from exc
        if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="access_groups JSON value must be an array of strings",
            )
        return [item.strip() for item in parsed if item.strip()]

    return [item.strip() for item in raw_value.split(",") if item.strip()]


def _sha256_bytes(content: bytes) -> str:
    return "sha256-" + hashlib.sha256(content).hexdigest()
