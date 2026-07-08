import hashlib
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.principal import Principal, get_principal
from app.domain.indexing import run_index_job
from app.domain.models import Document, DocumentChunk, IndexJob, KnowledgeSource
from app.domain.parsers import (
    DOCX_MIME_TYPE,
    MAX_EXTRACT_BYTES,
    PDF_MIME_TYPE,
    SUPPORTED_BINARY_MIME_TYPES,
    SUPPORTED_DOCUMENT_MIME_TYPES,
    SUPPORTED_TEXT_MIME_TYPES,
)
from app.domain.acl import CONFIDENTIALITY_RANK, confidentiality_rank, principal_can_access_document
from app.domain.vector import FakeVectorStore, VectorQuery, build_acl_filter, get_vector_store
from app.domain.schemas import (
    DocumentAclUpdate,
    DocumentCreate,
    DocumentChunkRead,
    DocumentRead,
    DocumentUploadRead,
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
from app.infra.authz import PRIVILEGED_ROLES, enforce_roles
from app.infra.object_store import document_object_key, get_object_store

router = APIRouter()


@router.get("/sources", response_model=list[KnowledgeSourceRead])
def list_sources(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> list[KnowledgeSource]:
    sources = list(
        db.scalars(select(KnowledgeSource).order_by(KnowledgeSource.created_at.desc()))
    )
    if "admin" in principal.roles:
        return sources
    # PARTIAL access control (NOT full ACL): KnowledgeSource has no per-source
    # access_groups/department ACL the way Document does -- only a
    # default_confidentiality_level. So this is a clearance-RANK filter ONLY: a non-admin
    # sees a source only when their clearance rank >= the source's default confidentiality
    # rank. It deliberately does NOT enforce group/department scoping for sources (none
    # exists in the schema); adding that requires a schema/migration change (out of scope).
    # Do not mistake this for document-style ACL enforcement.
    principal_rank = confidentiality_rank(principal.clearance_level)
    return [
        s
        for s in sources
        if principal_rank >= confidentiality_rank(s.default_confidentiality_level)
    ]


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
def list_documents(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> list[Document]:
    documents = list(
        db.scalars(
            select(Document)
            .where(Document.status != "archived")
            .order_by(Document.created_at.desc())
        )
    )
    if "admin" in principal.roles:
        return documents
    # Non-admins only see document metadata they're authorized to access.
    return [d for d in documents if principal_can_access_document(principal, d)]


@router.delete("/documents/{document_id}", response_model=DocumentRead)
def archive_document(
    document_id: str,
    reason: str = Query(default="archived via API"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> Document:
    """Soft-delete a document: mark archived (excluded from search/list) and purge its
    vectors from the store. Admin-gated; audited. Fail-closed: vector purge runs inside
    the request transaction before commit."""
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    enforce_roles(
        db, principal, PRIVILEGED_ROLES,
        action="document.archive", target_type="document", target_id=document_id,
    )

    document.status = "archived"
    for chunk in document.chunks:
        chunk.status = "archived"
    db.flush()
    get_vector_store().delete_document(document.id)

    write_audit_event(
        db,
        principal=principal,
        event_type="document.archived",
        target_type="document",
        target_id=document.id,
        reason=reason,
        payload={"knowledge_source_id": document.knowledge_source_id, "title": document.title},
    )
    db.commit()
    db.refresh(document)
    return document


@router.post("/documents/{document_id}/restore", response_model=DocumentRead)
def restore_document(
    document_id: str,
    reason: str = Query(default="restored via API"),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> Document:
    """Restore (unarchive) a soft-deleted document so it reappears in listings and
    ACL-scoped reads. Admin-gated; audited. 409 if the document is not currently
    archived.

    The document goes back to ``registered`` (not ``indexed``): that is the codebase's
    pre-index state — it is in ``SEARCHABLE_DOCUMENT_STATUSES`` (visible to authorized
    non-admins) and passes ``document_can_be_indexed`` so it can be re-indexed. Chunks
    become ``active``: visible in chunk listings, but excluded from retrieval (which
    requires ``indexed``) because their vectors are gone.

    Honest limitation: archiving purged this document's vectors from the store, and
    restore deliberately does NOT re-populate them (no vector-store side effect here,
    so there is nothing to fail-close around, unlike archive). The restored document is
    visible/listed again but not retrievable until a fresh index job runs
    (``POST /documents/{id}/index-jobs`` with ``force_reindex: true`` + ``/process``).
    """
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    enforce_roles(
        db, principal, PRIVILEGED_ROLES,
        action="document.restore", target_type="document", target_id=document_id,
    )

    if document.status != "archived":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Document is not archived"
        )

    document.status = "registered"
    for chunk in document.chunks:
        # "active" (not "indexed"): the chunk rows are visible again, but their vectors
        # were purged at archive time, so they must not be treated as searchable.
        chunk.status = "active"
    db.flush()

    write_audit_event(
        db,
        principal=principal,
        event_type="document.restored",
        target_type="document",
        target_id=document.id,
        reason=reason,
        payload={"knowledge_source_id": document.knowledge_source_id, "title": document.title},
    )
    db.commit()
    db.refresh(document)
    return document


@router.post("/documents", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
def register_document(
    payload: DocumentCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> Document:
    source = db.get(KnowledgeSource, payload.knowledge_source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge source not found")
    _validate_confidentiality(payload.confidentiality_level)

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


@router.patch("/documents/{document_id}/acl", response_model=DocumentRead)
def update_document_acl(
    document_id: str,
    payload: DocumentAclUpdate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    enforce_roles(
        db, principal, PRIVILEGED_ROLES,
        action="document.acl_update", target_type="document", target_id=document_id,
    )

    if payload.confidentiality_level.lower() not in CONFIDENTIALITY_RANK:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Unknown confidentiality_level",
        )

    before = {
        "access_groups": list(document.access_groups),
        "confidentiality_level": document.confidentiality_level,
    }
    new_groups = list(dict.fromkeys(g.strip() for g in payload.access_groups if g.strip()))
    if not new_groups:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="access_groups must not be empty",
        )

    document.access_groups = new_groups
    document.confidentiality_level = payload.confidentiality_level.lower()
    rank = confidentiality_rank(document.confidentiality_level)

    for chunk in document.chunks:
        snapshot = dict(chunk.acl_snapshot or {})
        snapshot["access_groups"] = new_groups
        snapshot["confidentiality_level"] = document.confidentiality_level
        chunk.acl_snapshot = snapshot

    db.flush()
    # Fail-closed: if Qdrant sync raises, the whole request rolls back.
    chunks_synced = get_vector_store().set_document_acl(
        document.id, access_groups=tuple(new_groups), confidentiality_rank=rank
    )

    write_audit_event(
        db,
        principal=principal,
        event_type="document.acl_changed",
        target_type="document",
        target_id=document.id,
        reason=payload.reason,
        payload={
            "before": before,
            "after": {
                "access_groups": new_groups,
                "confidentiality_level": document.confidentiality_level,
            },
            "chunks_synced": chunks_synced,
        },
    )
    db.commit()
    db.refresh(document)
    return document


@router.post(
    "/documents/upload",
    response_model=DocumentUploadRead,
    status_code=status.HTTP_201_CREATED,
)
def upload_document_and_index(
    knowledge_source_id: str = Form(...),
    title: str = Form(...),
    confidentiality_level: str = Form("internal"),
    access_groups: str = Form("all-employees"),
    effective_date: str | None = Form(None),
    embedding_model: str = Form("bge-m3"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> dict[str, Document | IndexJob]:
    source = db.get(KnowledgeSource, knowledge_source_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge source not found")

    filename = _safe_upload_filename(file.filename)
    raw = file.file.read()
    if len(raw) > MAX_EXTRACT_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File too large")

    mime_type = _upload_mime_type(file.content_type, filename)
    if mime_type not in SUPPORTED_DOCUMENT_MIME_TYPES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Unsupported file type")
    _validate_confidentiality(confidentiality_level)

    document = Document(
        knowledge_source_id=source.id,
        title=title.strip() or Path(filename).stem or filename,
        object_uri=f"upload://{filename}",
        checksum="sha256-" + hashlib.sha256(raw).hexdigest(),
        mime_type=mime_type,
        confidentiality_level=confidentiality_level,
        access_groups=_parse_access_groups(access_groups),
        status="registered",
        effective_date=effective_date,
    )
    db.add(document)
    db.flush()
    # Persist the original bytes to object storage (AF-009) when enabled, so the
    # document can be re-indexed later without re-uploading. No-op when disabled.
    object_store = get_object_store()
    if object_store is not None:
        object_store.put(document_object_key(document.id), raw)
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
            "upload_mime_type": document.mime_type,
        },
    )

    job = IndexJob(
        document_id=document.id,
        status="queued",
        stage="parse",
        config={
            "parser_profile": "upload-extract-text",
            "chunking": {"strategy": "line-heading", "chunk_size": 900, "chunk_overlap": 0},
            "embedding_model": embedding_model,
            "force_reindex": False,
            "source": "uploaded_file",
            "original_mime_type": mime_type,
            "original_filename": filename,
        },
        created_by=principal.user_id,
    )
    db.add(job)
    db.flush()

    run_index_job(
        db=db,
        document=document,
        job=job,
        principal=principal,
        source_text=_decode_uploaded_text(raw) if mime_type in SUPPORTED_TEXT_MIME_TYPES else None,
        source_bytes=raw if mime_type in SUPPORTED_BINARY_MIME_TYPES else None,
    )

    db.commit()
    db.refresh(document)
    db.refresh(job)
    return {"document": document, "index_job": job}


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

    source_text = payload.source_text
    source_bytes: bytes | None = None
    if source_text is None:
        raw = _fetch_object_bytes(document)
        if raw is not None:
            if document.mime_type in SUPPORTED_BINARY_MIME_TYPES:
                source_bytes = raw
            else:
                source_text = _decode_uploaded_text(raw)

    if source_text is None and source_bytes is None:
        job.started_at = datetime.now(UTC)
        job.status = "failed"
        job.stage = "parse"
        job.error_code = "SOURCE_CONTENT_UNAVAILABLE"
        job.error_message = (
            "No document content is available to index and none is stored in object storage."
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
            source_text=source_text,
            source_bytes=source_bytes,
            principal=principal,
        )

    db.commit()
    db.refresh(job)
    return job


@router.get("/index-jobs/{job_id}", response_model=IndexJobRead)
def get_index_job(
    job_id: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> IndexJob:
    job = db.get(IndexJob, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Index job not found")
    document = db.get(Document, job.document_id)
    if "admin" not in principal.roles and not (
        document is not None and principal_can_access_document(principal, document)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this index job"
        )
    return job


@router.get("/documents/{document_id}/chunks", response_model=list[DocumentChunkRead])
def list_document_chunks(
    document_id: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> list[DocumentChunk]:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if "admin" not in principal.roles and not principal_can_access_document(principal, document):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this document"
        )

    return list(
        db.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .where(DocumentChunk.status != "archived")
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


def _validate_confidentiality(level: str) -> None:
    if level.lower() not in CONFIDENTIALITY_RANK:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Unknown confidentiality_level",
        )


def _fetch_object_bytes(document: Document) -> bytes | None:
    """Fetch a document's original bytes from object storage, or None if unavailable."""
    store = get_object_store()
    if store is None:
        return None
    key = document_object_key(document.id)
    if not store.exists(key):
        return None
    return store.get(key)


def _parse_access_groups(value: str) -> list[str]:
    groups = [group.strip() for group in value.split(",") if group.strip()]
    return groups or ["all-employees"]


def _safe_upload_filename(filename: str | None) -> str:
    if not filename:
        return "uploaded-document"
    return filename.replace("\\", "/").split("/")[-1] or "uploaded-document"


def _upload_mime_type(content_type: str | None, filename: str) -> str:
    normalized_content_type = (content_type or "").split(";")[0].strip().lower()
    if normalized_content_type in SUPPORTED_DOCUMENT_MIME_TYPES:
        return normalized_content_type

    extension = Path(filename).suffix.casefold()
    if extension == ".pdf":
        return PDF_MIME_TYPE
    if extension == ".docx":
        return DOCX_MIME_TYPE
    if extension == ".md":
        return "text/markdown"
    if extension == ".txt":
        return "text/plain"
    return normalized_content_type or "application/octet-stream"


def _decode_uploaded_text(content: bytes) -> str:
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return content.decode("utf-8", errors="replace")
