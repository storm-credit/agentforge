from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.domain.models import AuditEvent
from app.domain.schemas import AuditEventRead

router = APIRouter()


@router.get("/events", response_model=list[AuditEventRead])
def list_audit_events(
    limit: int = Query(default=50, ge=1, le=200),
    event_type: str | None = Query(default=None, max_length=120),
    actor_id: str | None = Query(default=None, max_length=120),
    target_type: str | None = Query(default=None, max_length=80),
    target_id: str | None = Query(default=None, max_length=120),
    q: str | None = Query(default=None, min_length=1, max_length=120),
    db: Session = Depends(get_db),
) -> list[AuditEvent]:
    statement = select(AuditEvent)

    if event_type:
        statement = statement.where(AuditEvent.event_type == event_type)
    if actor_id:
        statement = statement.where(AuditEvent.actor_id == actor_id)
    if target_type:
        statement = statement.where(AuditEvent.target_type == target_type)
    if target_id:
        statement = statement.where(AuditEvent.target_id == target_id)
    if q:
        like_query = f"%{q}%"
        statement = statement.where(
            or_(
                AuditEvent.event_type.ilike(like_query),
                AuditEvent.actor_id.ilike(like_query),
                AuditEvent.actor_department.ilike(like_query),
                AuditEvent.target_type.ilike(like_query),
                AuditEvent.target_id.ilike(like_query),
                AuditEvent.reason.ilike(like_query),
            )
        )

    return list(db.scalars(statement.order_by(AuditEvent.created_at.desc()).limit(limit)))
