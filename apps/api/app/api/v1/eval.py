from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.principal import Principal, get_principal
from app.domain.model_routing import (
    ModelRoutingPolicyError,
    validate_model_route_summary,
    validate_model_routing_policy_ref,
)
from app.domain.models import EvalCaseResult, EvalRun
from app.domain.schemas import (
    EvalBaselineApproval,
    EvalCaseResultRead,
    EvalOverviewRead,
    EvalRunCreate,
    EvalRunRead,
    EvalRunWithResultsRead,
)
from app.infra.audit import write_audit_event

router = APIRouter()


@router.get("/overview", response_model=EvalOverviewRead)
def get_eval_overview(db: Session = Depends(get_db)) -> EvalOverviewRead:
    eval_run = _latest_eval_run(db)
    if eval_run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Eval run not found")

    return _overview(eval_run)


@router.get("/runs", response_model=list[EvalRunRead])
def list_eval_runs(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[EvalRun]:
    return list(db.scalars(select(EvalRun).order_by(EvalRun.created_at.desc()).limit(limit)))


@router.post("/runs", response_model=EvalRunWithResultsRead, status_code=status.HTTP_201_CREATED)
def create_eval_run(
    payload: EvalRunCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> EvalRun:
    _validate_eval_model_route_or_422(payload)
    passed = payload.passed and payload.failed_cases == 0 and not payload.setup_findings
    eval_run = EvalRun(
        corpus_id=payload.corpus_id,
        mode=payload.mode,
        status="passed" if passed else "needs_review",
        passed=passed,
        total_cases=payload.total_cases,
        passed_cases=payload.passed_cases,
        failed_cases=payload.failed_cases,
        suite_counts=dict(payload.suite_counts),
        setup_findings=list(payload.setup_findings),
        setup=dict(payload.setup),
        summary=_build_summary(payload),
        model_routing_policy_ref=payload.model_routing_policy_ref,
        budget_class=payload.budget_class,
        model_route_summary=dict(payload.model_route_summary),
        created_by=principal.user_id,
    )
    db.add(eval_run)
    db.flush()

    for result in payload.results:
        db.add(
            EvalCaseResult(
                eval_run_id=eval_run.id,
                case_id=result.case_id,
                suite=result.suite,
                expected_behavior=result.expected_behavior,
                passed=result.passed,
                findings=list(result.findings),
                run_id=result.run_id,
                status=result.status,
                citation_document_ids=list(result.citation_document_ids),
                retrieval_document_ids=list(result.retrieval_document_ids),
                retrieval_denied_count=result.retrieval_denied_count,
            )
        )

    write_audit_event(
        db,
        principal=principal,
        event_type="eval_run.created",
        target_type="eval_run",
        target_id=eval_run.id,
        payload={
            "corpus_id": eval_run.corpus_id,
            "mode": eval_run.mode,
            "passed": eval_run.passed,
            "total_cases": eval_run.total_cases,
            "failed_cases": eval_run.failed_cases,
            "budget_class": eval_run.budget_class,
            "model_routing_policy_ref": eval_run.model_routing_policy_ref,
        },
    )
    db.commit()
    return _get_eval_run_or_404(db, eval_run.id)


@router.get("/runs/latest", response_model=EvalRunWithResultsRead)
def get_latest_eval_run(db: Session = Depends(get_db)) -> EvalRun:
    eval_run = _latest_eval_run(db)
    if eval_run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Eval run not found")
    return eval_run


@router.get("/runs/current", response_model=EvalRunWithResultsRead)
def get_current_eval_run(db: Session = Depends(get_db)) -> EvalRun:
    eval_run = _latest_eval_run(db)
    if eval_run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Eval run not found")
    return eval_run


@router.get("/runs/{eval_run_id}", response_model=EvalRunWithResultsRead)
def get_eval_run(eval_run_id: str, db: Session = Depends(get_db)) -> EvalRun:
    return _get_eval_run_or_404(db, eval_run_id)


@router.get("/runs/{eval_run_id}/results", response_model=list[EvalCaseResultRead])
def list_eval_run_results(
    eval_run_id: str,
    db: Session = Depends(get_db),
) -> list[EvalCaseResult]:
    eval_run = _get_eval_run_or_404(db, eval_run_id)
    return list(eval_run.results)


@router.post("/runs/{eval_run_id}/approve-baseline", response_model=EvalRunRead)
def approve_eval_baseline(
    eval_run_id: str,
    payload: EvalBaselineApproval,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> EvalRun:
    eval_run = _get_eval_run_or_404(db, eval_run_id)
    eval_run.approved_baseline_at = datetime.now(UTC)
    eval_run.approved_baseline_by = principal.user_id
    write_audit_event(
        db,
        principal=principal,
        event_type="eval_run.baseline_approved",
        target_type="eval_run",
        target_id=eval_run.id,
        reason=payload.reason,
        payload={
            "corpus_id": eval_run.corpus_id,
            "passed": eval_run.passed,
            "failed_cases": eval_run.failed_cases,
        },
    )
    db.commit()
    db.refresh(eval_run)
    return eval_run


def _latest_eval_run(db: Session) -> EvalRun | None:
    return db.scalar(
        select(EvalRun).options(selectinload(EvalRun.results)).order_by(EvalRun.created_at.desc())
    )


def _get_eval_run_or_404(db: Session, eval_run_id: str) -> EvalRun:
    eval_run = db.scalar(
        select(EvalRun).options(selectinload(EvalRun.results)).where(EvalRun.id == eval_run_id)
    )
    if eval_run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Eval run not found")
    return eval_run


def _overview(eval_run: EvalRun) -> EvalOverviewRead:
    return EvalOverviewRead(
        run=EvalRunRead.model_validate(eval_run),
        suite_counts=eval_run.suite_counts,
        results=[EvalCaseResultRead.model_validate(result) for result in eval_run.results],
    )


def _build_summary(payload: EvalRunCreate) -> dict:
    answer_cases = [result for result in payload.results if result.expected_behavior == "answer"]
    citation_coverage = (
        sum(1 for result in answer_cases if result.citation_document_ids) / len(answer_cases)
        if answer_cases
        else 0
    )
    trace_completeness = (
        sum(1 for result in payload.results if result.run_id) / len(payload.results)
        if payload.results
        else 0
    )
    acl_violation_count = sum(
        1
        for result in payload.results
        for finding in result.findings
        if "forbidden" in finding.casefold()
    )

    return {
        **payload.summary,
        "pass_rate": payload.passed_cases / payload.total_cases if payload.total_cases else 0,
        "citation_coverage": citation_coverage,
        "trace_completeness": trace_completeness,
        "acl_violation_count": acl_violation_count,
        "budget_class": payload.budget_class,
        "model_routing_policy_ref": payload.model_routing_policy_ref,
        "model_route_summary": payload.model_route_summary,
    }


def _validate_eval_model_route_or_422(payload: EvalRunCreate) -> None:
    try:
        validate_model_routing_policy_ref(payload.model_routing_policy_ref)
        validate_model_route_summary(
            payload.model_route_summary,
            budget_class=payload.budget_class,
        )
    except ModelRoutingPolicyError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc
