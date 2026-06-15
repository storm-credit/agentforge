from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.principal import Principal, get_principal
from app.domain.models import AuditEvent
from app.domain.schemas import AuditEventRead
from app.infra.audit import write_audit_event
from app.infra.authz import AUDIT_READ_ROLES, enforce_roles

router = APIRouter()


@router.get("/events", response_model=list[AuditEventRead])
def list_audit_events(
    event_type: str | None = Query(default=None),
    target_type: str | None = Query(default=None),
    target_id: str | None = Query(default=None),
    actor_id: str | None = Query(default=None),
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> list[AuditEvent]:
    """Read the audit trail. Admin-scoped, and the query itself is audited."""
    enforce_roles(db, principal, AUDIT_READ_ROLES, action="audit_log.read")

    statement = select(AuditEvent)
    if event_type is not None:
        statement = statement.where(AuditEvent.event_type == event_type)
    if target_type is not None:
        statement = statement.where(AuditEvent.target_type == target_type)
    if target_id is not None:
        statement = statement.where(AuditEvent.target_id == target_id)
    if actor_id is not None:
        statement = statement.where(AuditEvent.actor_id == actor_id)
    if since is not None:
        statement = statement.where(AuditEvent.created_at >= since)
    if until is not None:
        statement = statement.where(AuditEvent.created_at <= until)
    statement = statement.order_by(AuditEvent.created_at.desc()).limit(limit).offset(offset)

    events = list(db.scalars(statement))

    # The act of reading the audit trail is itself audited (audit-log access policy).
    write_audit_event(
        db,
        principal=principal,
        event_type="audit_log.viewed",
        target_type="audit_log",
        target_id="query",
        payload={
            "filters": {
                "event_type": event_type,
                "target_type": target_type,
                "target_id": target_id,
                "actor_id": actor_id,
            },
            "result_count": len(events),
            "limit": limit,
            "offset": offset,
        },
    )
    db.commit()
    return events
