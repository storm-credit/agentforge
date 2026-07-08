"""Persisted eval-harness runs: record a report, browse history.

Authorization model:
- **Write** (``POST /runs``) is gated to ``PRIVILEGED_ROLES`` like every other platform
  mutation — recording an eval run is an operator/admin act (the harness runs with an
  operator header), and an open write endpoint would let anyone pollute the quality
  history that go/no-go decisions read from.
- **Reads** are open to any authenticated principal (unlike ``/audit/events``): the
  report contains aggregate quality metrics and synthetic eval-corpus cases — no PII,
  no user activity, no security-audit content — and developers need the history to see
  whether retrieval/answer quality moved.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.principal import Principal, get_principal
from app.domain.models import EvalRun
from app.domain.schemas import EvalRunCreate, EvalRunRead, EvalRunSummary
from app.infra.audit import write_audit_event
from app.infra.authz import PRIVILEGED_ROLES, enforce_roles

router = APIRouter()

# Headline metrics surfaced in the list view (full report stays in the detail view).
_SUMMARY_METRICS = (
    "total",
    "citation_pct",
    "useful_answer_pct",
    "refusal_discipline_pct",
    "faithfulness_pct",
    "faithfulness_threshold",
)


def _to_summary(run: EvalRun) -> EvalRunSummary:
    report = run.report or {}
    metrics = {
        key: value
        for key in _SUMMARY_METRICS
        if isinstance(value := report.get(key), (int, float)) and not isinstance(value, bool)
    }
    return EvalRunSummary(
        id=run.id,
        corpus_id=run.corpus_id,
        label=run.label,
        created_by=run.created_by,
        created_at=run.created_at,
        **metrics,
    )


@router.post("/runs", response_model=EvalRunRead, status_code=status.HTTP_201_CREATED)
def create_eval_run(
    payload: EvalRunCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> EvalRun:
    """Persist one eval-harness report. Privileged (operator/admin) mutation."""
    enforce_roles(
        db, principal, PRIVILEGED_ROLES,
        action="eval_run.create", target_type="eval_run",
    )

    run = EvalRun(
        corpus_id=payload.corpus_id,
        label=payload.label,
        report=payload.report,
        created_by=principal.user_id,
    )
    db.add(run)
    db.flush()
    write_audit_event(
        db,
        principal=principal,
        event_type="eval_run.recorded",
        target_type="eval_run",
        target_id=run.id,
        payload={
            "corpus_id": run.corpus_id,
            "label": run.label,
            "case_count": len(payload.report.get("cases") or []),
        },
    )
    db.commit()
    db.refresh(run)
    return run


@router.get("/runs", response_model=list[EvalRunSummary])
def list_eval_runs(
    corpus_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> list[EvalRunSummary]:
    """List past eval runs, newest first, as lightweight summaries (no cases array)."""
    statement = select(EvalRun)
    if corpus_id is not None:
        statement = statement.where(EvalRun.corpus_id == corpus_id)
    statement = statement.order_by(EvalRun.created_at.desc()).limit(limit).offset(offset)
    return [_to_summary(run) for run in db.scalars(statement)]


@router.get("/runs/{run_id}", response_model=EvalRunRead)
def get_eval_run(
    run_id: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> EvalRun:
    """Full detail for one eval run, including the complete report (cases included)."""
    run = db.get(EvalRun, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Eval run not found")
    return run
