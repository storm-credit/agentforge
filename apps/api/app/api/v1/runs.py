from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.principal import Principal, get_principal
from app.domain.citations import CitationValidationResult, validate_run_citations
from app.domain.model_routing import (
    MODEL_ROUTING_POLICY_REF,
    ModelRoutingPolicyError,
    runtime_policy_from_agent_config,
)
from app.domain.models import Agent, AgentVersion, Document, RetrievalHit, Run, RunStep
from app.domain.schemas import (
    RetrievalHitRead,
    RunCreate,
    RunRead,
    RunStepRead,
)
from app.domain.vector import VectorQuery, VectorSearchResult, build_acl_filter
from app.infra.audit import write_audit_event
from app.infra.vector_store import get_vector_store

router = APIRouter()


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
    try:
        budget_class, model_route = runtime_policy_from_agent_config(agent_version.config)
    except ModelRoutingPolicyError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

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
            "budget_class": budget_class,
            "model_routing_policy_ref": MODEL_ROUTING_POLICY_REF,
            "model_route_summary": model_route,
        },
        started_at=started_at,
    )
    db.add(run)
    db.flush()

    guard_decision = _input_guard_decision(payload.input.message)
    if guard_decision is not None:
        outcome = guard_decision["outcome"]
        _add_step(
            db,
            run=run,
            order=1,
            step_type="guard_input",
            input_summary={"message_length": len(payload.input.message)},
            output_summary={
                "allowed": False,
                "risk_level": "blocked",
                "outcome": outcome,
                "reason": guard_decision["reason"],
                "route_stage": "security_precheck",
                "model_tier": model_route["security_precheck"]["tier"],
            },
            started_at=started_at,
            status="failed",
            error_code=guard_decision["code"],
            error_message=guard_decision["message"],
        )
        _add_step(
            db,
            run=run,
            order=2,
            step_type="guard_output",
            input_summary={"answer_length": len(guard_decision["answer"])},
            output_summary={
                "security_finalcheck_pass": False,
                "citation_count": 0,
                "outcome": outcome,
                "route_stage": "security_finalcheck",
                "model_tier": model_route["security_finalcheck"]["tier"],
            },
            status="failed",
            error_code=guard_decision["code"],
            error_message=guard_decision["message"],
        )
        run.status = "failed"
        run.answer = guard_decision["answer"]
        run.citations = []
        run.retrieval_denied_count = 0
        run.guardrail = {
            "acl_filter_applied": False,
            "citation_required": bool(agent_version.config.get("citation_required", True)),
            "citation_count": 0,
            "citation_validation_pass": False,
            "citation_validation_error_code": guard_decision["code"],
            "citation_validation_missing_fields": [],
            "pii_masked": False,
            "security_finalcheck_pass": False,
            "outcome": outcome,
            "input_guard_pass": False,
            "input_guard_reason": guard_decision["reason"],
            "budget_class": budget_class,
            "model_routing_policy_ref": MODEL_ROUTING_POLICY_REF,
            "model_route_summary": model_route,
        }
        run.finished_at = datetime.now(UTC)
        run.latency_ms = max(1, int((perf_counter() - timer_start) * 1000))
        write_audit_event(
            db,
            principal=principal,
            event_type=f"run.{outcome}",
            target_type="run",
            target_id=run.id,
            payload={
                "agent_id": run.agent_id,
                "agent_version_id": run.agent_version_id,
                "query_length": len(payload.input.message),
                "reason": guard_decision["reason"],
                "step_count": 2,
                "budget_class": budget_class,
                "model_routing_policy_ref": MODEL_ROUTING_POLICY_REF,
            },
        )
        db.commit()
        db.refresh(run)
        return run

    _add_step(
        db,
        run=run,
        order=1,
        step_type="guard_input",
        input_summary={"message_length": len(payload.input.message)},
        output_summary={
            "allowed": True,
            "risk_level": "low",
            "route_stage": "security_precheck",
            "model_tier": model_route["security_precheck"]["tier"],
        },
        started_at=started_at,
    )

    vector_result = _search_authorized_context(
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
            "vector_adapter": vector_result.adapter_name,
            "route_stage": "retriever",
            "model_tier": model_route["retriever"]["tier"],
        },
    )

    citations = []
    for rank, hit in enumerate(vector_result.hits, start=1):
        citation_locator = hit.citation_locator or hit.citation
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
                    "vector_adapter": vector_result.adapter_name,
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

    run.answer = _build_synthetic_answer(len(citations))
    run.citations = citations
    run.retrieval_denied_count = vector_result.denied_count
    outcome = _runtime_outcome(
        citation_count=len(citations), denied_count=vector_result.denied_count
    )
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
        "outcome": outcome,
        "input_guard_pass": True,
        "budget_class": budget_class,
        "model_routing_policy_ref": MODEL_ROUTING_POLICY_REF,
        "model_route_summary": model_route,
    }

    next_step_order = 3
    if citations:
        _add_step(
            db,
            run=run,
            order=next_step_order,
            step_type="generator",
            input_summary={"context_count": len(citations)},
            output_summary={
                "answer_length": len(run.answer),
                "citation_count": len(citations),
                "mode": "synthetic",
                "route_stage": "answer_generator",
                "model_tier": model_route["answer_generator"]["tier"],
            },
        )
        next_step_order += 1
    else:
        run.guardrail["answer_source"] = "safe-fallback"

    _add_step(
        db,
        run=run,
        order=next_step_order,
        step_type="citation_validator",
        input_summary={
            "citation_required": citation_validation.required,
            "citation_count": citation_validation.citation_count,
        },
        output_summary={
            **_citation_validation_summary(citation_validation),
            "route_stage": "critic",
            "model_tier": model_route["critic"]["tier"],
        },
        status="succeeded" if citation_validation.passed else "failed",
        error_code=citation_validation.error_code,
        error_message=citation_validation.error_message,
    )
    next_step_order += 1
    _add_step(
        db,
        run=run,
        order=next_step_order,
        step_type="guard_output",
        input_summary={"answer_length": len(run.answer)},
        output_summary={
            "security_finalcheck_pass": citation_validation.passed,
            "citation_count": len(citations),
            "route_stage": "security_finalcheck",
            "model_tier": model_route["security_finalcheck"]["tier"],
        },
        status="succeeded" if citation_validation.passed else "failed",
        error_code=citation_validation.error_code,
        error_message=citation_validation.error_message,
    )
    next_step_order += 1

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
            "step_count": next_step_order - 1,
            "budget_class": budget_class,
            "model_routing_policy_ref": MODEL_ROUTING_POLICY_REF,
            "vector_adapter": vector_result.adapter_name,
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
        db.scalars(select(RunStep).where(RunStep.run_id == run_id).order_by(RunStep.step_order))
    )


@router.get("/{run_id}/retrieval-hits", response_model=list[RetrievalHitRead])
def list_run_retrieval_hits(run_id: str, db: Session = Depends(get_db)) -> list[RetrievalHit]:
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    return list(
        db.scalars(
            select(RetrievalHit)
            .where(RetrievalHit.run_id == run_id)
            .order_by(RetrievalHit.rank_original)
        )
    )


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
) -> VectorSearchResult:
    documents = list(
        db.scalars(
            select(Document)
            .options(selectinload(Document.chunks))
            .order_by(Document.created_at.desc())
        )
    )
    return get_vector_store().search(
        query=VectorQuery(
            query_text=query_text,
            knowledge_source_ids=tuple(knowledge_source_ids),
            top_k=top_k,
        ),
        documents=documents,
        acl_filter=acl_filter,
    )


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


def _build_synthetic_answer(citation_count: int) -> str:
    if citation_count == 0:
        return "No authorized context was available for this runtime run."

    return f"Synthetic runtime response based on {citation_count} authorized citation(s)."


def _runtime_outcome(*, citation_count: int, denied_count: int) -> str:
    if citation_count > 0:
        return "answer"
    if denied_count > 0:
        return "policy_denied"
    return "no_context"


def _input_guard_decision(message: str) -> dict[str, str] | None:
    normalized = " ".join(message.casefold().split())
    guard_checks = (
        (
            "no_context",
            "NO_CONTEXT_HALLUCINATION_REQUEST",
            "no_context",
            "No grounded context is available, and the runtime will not make up an answer.",
            ("make up", "cannot find"),
        ),
        (
            "refuse",
            "WRITE_ACTION_NOT_SUPPORTED",
            "write_action",
            "Write actions are not supported by this document RAG runtime.",
            ("update", "record"),
        ),
        (
            "refuse",
            "PERSONAL_DATA_REQUEST",
            "personal_data",
            "Personal data cannot be disclosed by this runtime.",
            ("personal phone number",),
        ),
        (
            "refuse",
            "PROMPT_INJECTION_REFUSED",
            "prompt_injection",
            "Instruction override requests do not change Agent Forge policy.",
            ("bypass", "acl"),
        ),
    )
    for outcome, code, reason, answer, required_terms in guard_checks:
        if all(term in normalized for term in required_terms):
            return {
                "outcome": outcome,
                "code": code,
                "reason": reason,
                "message": answer,
                "answer": answer,
            }
    return None
