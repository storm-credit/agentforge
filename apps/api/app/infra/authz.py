"""Role-based authorization for privileged mutations.

Header-stub principal for now (SSO not wired), but enforcing on the *value* of
``principal.roles`` is independent of how roles are populated (header today, SSO claim
later). Denied attempts are audited (``policy.denied``) for forensics.
"""

from __future__ import annotations

from collections.abc import Iterable

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.principal import Principal
from app.infra.audit import write_audit_event

# Roles permitted to perform privileged platform mutations (publish/validate, ACL change).
PRIVILEGED_ROLES: frozenset[str] = frozenset({"admin", "platform-admin", "knowledge-manager"})

# Reading the audit trail is narrower than mutation rights (least privilege): a
# knowledge-manager can change ACLs but should not enumerate org-wide who-did-what.
AUDIT_READ_ROLES: frozenset[str] = frozenset({"admin", "platform-admin", "security-auditor"})


def enforce_roles(
    db: Session,
    principal: Principal,
    allowed: Iterable[str],
    *,
    action: str,
    target_type: str = "endpoint",
    target_id: str = "",
) -> None:
    """Allow if the principal holds any ``allowed`` role; otherwise audit + 403."""
    allowed_set = set(allowed)
    if allowed_set & set(principal.roles):
        return
    write_audit_event(
        db,
        principal=principal,
        event_type="policy.denied",
        target_type=target_type,
        target_id=target_id or action,
        reason=f"action {action} requires one of {sorted(allowed_set)}",
        payload={"action": action, "principal_roles": list(principal.roles)},
    )
    db.commit()
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Insufficient role for this action",
    )
