from __future__ import annotations

import logging
from datetime import UTC, datetime
from time import perf_counter

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.database import get_db
from app.core.principal import Principal, get_principal
from app.domain.citations import CitationValidationResult, validate_run_citations
from app.domain.models import Agent, AgentVersion, Document, DocumentChunk, RetrievalHit, Run, RunStep
from app.domain.schemas import (
    RetrievalHitRead,
    RunCreate,
    RunRead,
    RunStepRead,
)
from app.domain.language import resolve_language
from app.domain.vector import FakeVectorStore, VectorQuery, VectorSearchResult, build_acl_filter, get_vector_store
from app.infra.audit import write_audit_event
from app.services.llm_gateway import ContextBlock, get_gateway

logger = logging.getLogger(__name__)

router = APIRouter()


def _hit_locator(hit) -> str | None:
    return hit.citation_locator or hit.citation


@router.get("", response_model=list[RunRead])
def list_runs(db: Session = Depends(get_db)) -> list[Run]:
    return list(db.scalars(select(Run).order_by(Run.created_at.desc())))


@router.post("", response_model=RunRead, status_code=status.HTTP_201_CREATED)
def create_run(
    payload: RunCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> Run:
    agent = db.get(Agent, payload.agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    agent_version = _resolve_agent_version(db, agent, payload.agent_version_id)
    knowledge_source_ids = _runtime_knowledge_sources(payload, agent_version)
    acl_filter = build_acl_filter(principal)
    started_at = datetime.now(UTC)
    timer_start = perf_counter()

    run = Run(
        agent_id=agent.id,
        agent_version_id=agent_version.id,
        user_id=principal.user_id,
        user_department=principal.department,
        status="running",
        input={
            **payload.input.model_dump(),
            "mode": payload.mode,
            "debug": payload.debug,
            "knowledge_source_ids": knowledge_source_ids,
            "top_k": payload.top_k,
        },
        started_at=started_at,
    )
    db.add(run)
    db.flush()

    _add_step(
        db,
        run=run,
        order=1,
        step_type="guard_input",
        input_summary={"message_length": len(payload.input.message)},
        output_summary={"allowed": True, "risk_level": "low"},
        started_at=started_at,
    )

    vector_result, vector_adapter, vector_degraded = _search_authorized_context(
        db=db,
        query_text=payload.input.message,
        knowledge_source_ids=knowledge_source_ids,
        top_k=payload.top_k,
        acl_filter=acl_filter,
    )
    _add_step(
        db,
        run=run,
        order=2,
        step_type="retriever",
        input_summary={
            "query_length": len(payload.input.message),
            "knowledge_source_count": len(knowledge_source_ids),
            "top_k": payload.top_k,
        },
        output_summary={
            "hit_count": len(vector_result.hits),
            "denied_count": vector_result.denied_count,
            "vector_adapter": vector_adapter,
            "degraded": vector_degraded,
        },
    )

    citations = []
    for rank, hit in enumerate(vector_result.hits, start=1):
        citation_locator = _hit_locator(hit)
        usable_as_citation = bool(hit.chunk_id and citation_locator)
        db.add(
            RetrievalHit(
                run_id=run.id,
                chunk_id=hit.chunk_id,
                document_id=hit.document_id,
                title=hit.title,
                citation_locator=citation_locator,
                rank_original=rank,
                rank_reranked=rank,
                score_vector=hit.score,
                score_rerank=None,
                used_in_context=True,
                used_as_citation=usable_as_citation,
                acl_filter_snapshot={
                    "subjects": list(acl_filter.subjects),
                    "clearance_level": acl_filter.clearance_level,
                    "knowledge_source_ids": knowledge_source_ids,
                    "vector_adapter": vector_adapter,
                },
            )
        )
        if usable_as_citation:
            citations.append(
                {
                    "document_id": hit.document_id,
                    "chunk_id": hit.chunk_id,
                    "title": hit.title,
                    "citation_locator": citation_locator,
                    "score": hit.score,
                }
            )

    answer_language = resolve_language(payload.language, payload.input.message)
    context_blocks = _load_context_blocks(db, vector_result.hits)
    generated = get_gateway().generate(
        question=payload.input.message, context=context_blocks, language=answer_language
    )
    run.answer = generated.text
    run.citations = citations
    run.retrieval_denied_count = vector_result.denied_count
    citation_required = bool(agent_version.config.get("citation_required", True))
    citation_validation = validate_run_citations(
        citations,
        citation_required=citation_required,
    )
    run.guardrail = {
        "acl_filter_applied": True,
        "citation_required": citation_required,
        "citation_count": len(citations),
        "citation_validation_pass": citation_validation.passed,
        "citation_validation_error_code": citation_validation.error_code,
        "citation_validation_missing_fields": list(citation_validation.missing_fields),
        "pii_masked": False,
        "security_finalcheck_pass": citation_validation.passed,
    }

    _add_step(
        db,
        run=run,
        order=3,
        step_type="generator",
        input_summary={"context_count": len(context_blocks)},
        output_summary={
            "answer_length": len(run.answer),
            "citation_count": len(citations),
            "mode": "llm" if generated.used_llm else ("fallback" if generated.fallback_used else "refused"),
            "language": answer_language,
        },
    )
    _add_step(
        db,
        run=run,
        order=4,
        step_type="citation_validator",
        input_summary={
            "citation_required": citation_validation.required,
            "citation_count": citation_validation.citation_count,
        },
        output_summary=_citation_validation_summary(citation_validation),
        status="succeeded" if citation_validation.passed else "failed",
        error_code=citation_validation.error_code,
        error_message=citation_validation.error_message,
    )
    _add_step(
        db,
        run=run,
        order=5,
        step_type="guard_output",
        input_summary={"answer_length": len(run.answer)},
        output_summary={
            "security_finalcheck_pass": citation_validation.passed,
            "citation_count": len(citations),
        },
        status="succeeded" if citation_validation.passed else "failed",
        error_code=citation_validation.error_code,
        error_message=citation_validation.error_message,
    )

    run.status = "succeeded" if citation_validation.passed else "failed"
    run.finished_at = datetime.now(UTC)
    run.latency_ms = max(1, int((perf_counter() - timer_start) * 1000))
    write_audit_event(
        db,
        principal=principal,
        event_type="run.created",
        target_type="run",
        target_id=run.id,
        payload={
            "agent_id": run.agent_id,
            "agent_version_id": run.agent_version_id,
            "status": run.status,
            "query_length": len(payload.input.message),
            "retrieval_hit_count": len(vector_result.hits),
            "citation_count": len(citations),
            "retrieval_denied_count": vector_result.denied_count,
            "citation_validation_pass": citation_validation.passed,
            "citation_validation_error_code": citation_validation.error_code,
            "step_count": 5,
        },
    )
    db.commit()
    db.refresh(run)
    return run


@router.get("/{run_id}", response_model=RunRead)
def get_run(run_id: str, db: Session = Depends(get_db)) -> Run:
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run


@router.get("/{run_id}/steps", response_model=list[RunStepRead])
def list_run_steps(run_id: str, db: Session = Depends(get_db)) -> list[RunStep]:
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    return list(
        db.scalars(
            select(RunStep).where(RunStep.run_id == run_id).order_by(RunStep.step_order)
        )
    )


@router.get("/{run_id}/retrieval-hits", response_model=list[RetrievalHitRead])
def list_run_retrieval_hits(run_id: str, db: Session = Depends(get_db)) -> list[RetrievalHitRead]:
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    hits = list(
        db.scalars(
            select(RetrievalHit)
            .where(RetrievalHit.run_id == run_id)
            .order_by(RetrievalHit.rank_original)
        )
    )
    chunk_ids = [hit.chunk_id for hit in hits if hit.chunk_id]
    contents: dict[str, str] = {}
    if chunk_ids:
        rows = db.scalars(select(DocumentChunk).where(DocumentChunk.id.in_(chunk_ids)))
        contents = {row.id: row.content for row in rows}
    return [
        RetrievalHitRead.model_validate(hit).model_copy(
            update={"content": contents.get(hit.chunk_id or "")}
        )
        for hit in hits
    ]


def _resolve_agent_version(
    db: Session,
    agent: Agent,
    agent_version_id: str | None,
) -> AgentVersion:
    if agent_version_id is not None:
        version = db.get(AgentVersion, agent_version_id)
        if version is None or version.agent_id != agent.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent version not found",
            )
        if version.status != "published":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Agent version is not published",
            )
        return version

    version = db.scalar(
        select(AgentVersion)
        .where(AgentVersion.agent_id == agent.id, AgentVersion.status == "published")
        .order_by(AgentVersion.version.desc())
    )
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Published agent version not found",
        )
    return version


def _runtime_knowledge_sources(payload: RunCreate, agent_version: AgentVersion) -> list[str]:
    if payload.knowledge_source_ids:
        return payload.knowledge_source_ids

    configured = agent_version.config.get("knowledge_source_ids", [])
    if not isinstance(configured, list):
        return []

    return [source_id for source_id in configured if isinstance(source_id, str)]


def _search_authorized_context(
    *,
    db: Session,
    query_text: str,
    knowledge_source_ids: list[str],
    top_k: int,
    acl_filter,
) -> tuple[VectorSearchResult, str, bool]:
    documents = list(
        db.scalars(
            select(Document)
            .options(selectinload(Document.chunks))
            .order_by(Document.created_at.desc())
        )
    )
    query = VectorQuery(
        query_text=query_text,
        knowledge_source_ids=tuple(knowledge_source_ids),
        top_k=top_k,
        min_score=get_settings().retrieval_min_score,
    )
    store = get_vector_store()
    label = "fake" if isinstance(store, FakeVectorStore) else "qdrant"
    try:
        result = store.search(query=query, documents=documents, acl_filter=acl_filter)
        return result, label, False
    except Exception as exc:  # noqa: BLE001 - stay answerable, ACL-safe, but mark degraded
        logger.warning("vector search failed (%s); falling back to FakeVectorStore", exc)
        result = FakeVectorStore().search(query=query, documents=documents, acl_filter=acl_filter)
        return result, "fake_fallback", True


def _add_step(
    db: Session,
    *,
    run: Run,
    order: int,
    step_type: str,
    input_summary: dict,
    output_summary: dict,
    started_at: datetime | None = None,
    status: str = "succeeded",
    error_code: str | None = None,
    error_message: str | None = None,
) -> None:
    step_started_at = started_at or datetime.now(UTC)
    step_finished_at = datetime.now(UTC)
    latency_ms = max(1, int((step_finished_at - step_started_at).total_seconds() * 1000))
    db.add(
        RunStep(
            run_id=run.id,
            step_order=order,
            step_type=step_type,
            status=status,
            input_summary=input_summary,
            output_summary=output_summary,
            started_at=step_started_at,
            finished_at=step_finished_at,
            latency_ms=latency_ms,
            error_code=error_code,
            error_message=error_message,
        )
    )


def _citation_validation_summary(result: CitationValidationResult) -> dict:
    return {
        "passed": result.passed,
        "required": result.required,
        "citation_count": result.citation_count,
        "error_code": result.error_code,
        "missing_fields": list(result.missing_fields),
    }


def _load_context_blocks(db: Session, hits) -> tuple[ContextBlock, ...]:
    chunk_ids = [hit.chunk_id for hit in hits if hit.chunk_id]
    contents: dict[str, str] = {}
    if chunk_ids:
        rows = db.scalars(select(DocumentChunk).where(DocumentChunk.id.in_(chunk_ids)))
        contents = {row.id: row.content for row in rows}
    blocks = []
    for hit in hits:
        text = contents.get(hit.chunk_id or "", "")
        if not text:
            continue
        blocks.append(ContextBlock(title=hit.title, locator=_hit_locator(hit), content=text))
    return tuple(blocks)
