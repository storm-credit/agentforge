from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.principal import Principal, get_principal
from app.domain.acl import principal_can_access_document
from app.domain.models import Document, KnowledgeSource
from app.domain.schemas import (
    DocumentCreate,
    DocumentRead,
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


@router.post("/retrieval/preview", response_model=RetrievalPreviewResponse)
def preview_retrieval(
    payload: RetrievalPreviewRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> RetrievalPreviewResponse:
    statement = select(Document).order_by(Document.created_at.desc())
    if payload.knowledge_source_ids:
        statement = statement.where(Document.knowledge_source_id.in_(payload.knowledge_source_ids))

    documents = list(db.scalars(statement))
    allowed_documents = [
        document for document in documents if principal_can_access_document(principal, document)
    ]
    denied_count = len(documents) - len(allowed_documents)

    hits = [
        RetrievalPreviewHit(
            document_id=document.id,
            knowledge_source_id=document.knowledge_source_id,
            title=document.title,
            confidentiality_level=document.confidentiality_level,
            access_groups=document.access_groups,
            score=_lexical_score(payload.query, document),
            citation=f"{document.title} ({document.effective_date or 'undated'})",
        )
        for document in allowed_documents
    ]
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


def _lexical_score(query: str, document: Document) -> float:
    query_terms = {term.casefold() for term in query.split() if term.strip()}
    title_terms = {term.casefold() for term in document.title.split() if term.strip()}
    if not query_terms:
        return 0.0
    overlap = len(query_terms.intersection(title_terms))
    return round(overlap / len(query_terms), 4)
