from sqlalchemy.orm import Session

from app.core.principal import Principal
from app.domain.models import AuditEvent


def write_audit_event(
    db: Session,
    *,
    principal: Principal,
    event_type: str,
    target_type: str,
    target_id: str,
    reason: str = "",
    payload: dict | None = None,
) -> AuditEvent:
    event = AuditEvent(
        event_type=event_type,
        actor_id=principal.user_id,
        actor_department=principal.department,
        target_type=target_type,
        target_id=target_id,
        reason=reason,
        payload=payload or {},
    )
    db.add(event)
    return event

