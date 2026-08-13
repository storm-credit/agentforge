from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.principal import Principal, get_principal
from app.domain.models import Agent, AgentVersion
from app.domain.schemas import (
    AgentCreate,
    AgentRead,
    AgentUpdate,
    AgentVersionCreate,
    AgentVersionRead,
    AgentVersionValidate,
)
from app.infra.audit import write_audit_event
from app.infra.authz import PRIVILEGED_ROLES, enforce_roles

router = APIRouter()


def _is_builder(principal: Principal) -> bool:
    """May this principal see unpublished agents and their draft/validated versions?

    RULE (WO-2026-08-13-ROLE-READ-COHERENCE): agent build-state visibility is scoped to
    PRIVILEGED_ROLES -- the exact set that may already create, update, validate and publish
    agent versions. The gate these reads apply is a PUBLICATION-STATUS gate ("hide work in
    progress"), NOT an ACL: Agent and AgentVersion carry no access_groups/clearance, so this
    widens no ACL bypass. Every non-privileged caller (the default `developer` principal
    included) is unaffected and still sees published agents only.

    Why this is not a privilege increase for platform-admin / knowledge-manager: both roles
    can ALREADY read exactly this data through mutations they hold, on any id, with no
    publication-status check -- `PATCH /agents/{id}` with an empty body returns a draft
    agent's full record, and `POST /agents/versions/{id}/validate` returns any version's full
    config. Those paths merely add an audit event and (for validate) a status change. So the
    previous literal "admin" read gate did not withhold anything from these roles; it only
    forced them to use a mutating call to read, and denied them ENUMERATION -- the one step
    that turns "may publish version X" into a workflow that can actually be started.
    """
    return bool(PRIVILEGED_ROLES.intersection(principal.roles))


@router.get("", response_model=list[AgentRead])
def list_agents(
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> list[Agent]:
    # Builders (PRIVILEGED_ROLES) see every agent; everyone else only published ones
    # (drafts/validated configs — including their system prompts and wired knowledge ids —
    # stay hidden). See _is_builder for why this set, not the literal "admin".
    query = select(Agent).order_by(Agent.created_at.desc())
    if not _is_builder(principal):
        query = query.where(Agent.status == "published")
    # Unlike list_documents/list_sources, the publish-status scoping here is already a
    # SQL WHERE (no Python post-filter), so LIMIT/OFFSET can safely live in SQL: the
    # window is computed on the exact set the caller is allowed to see.
    return list(db.scalars(query.limit(limit).offset(offset)))


@router.get("/{agent_id}", response_model=AgentRead)
def get_agent(
    agent_id: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> Agent:
    agent = db.get(Agent, agent_id)
    # 404 (not 403) for unpublished agents so a non-builder can't even learn they exist.
    # Builder = PRIVILEGED_ROLES, the set that may already update/publish this agent; see
    # _is_builder for the rule and for why this is not a read-privilege increase.
    if agent is None or (not _is_builder(principal) and agent.status != "published"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return agent


@router.post("", response_model=AgentRead, status_code=status.HTTP_201_CREATED)
def create_agent(
    payload: AgentCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> Agent:
    agent = Agent(**payload.model_dump())
    db.add(agent)
    db.flush()
    write_audit_event(
        db,
        principal=principal,
        event_type="agent.created",
        target_type="agent",
        target_id=agent.id,
        payload={"name": agent.name, "owner_department": agent.owner_department},
    )
    db.commit()
    db.refresh(agent)
    return agent


@router.patch("/{agent_id}", response_model=AgentRead)
def update_agent(
    agent_id: str,
    payload: AgentUpdate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> Agent:
    agent = db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    enforce_roles(
        db, principal, PRIVILEGED_ROLES,
        action="agent.update", target_type="agent", target_id=agent_id,
    )

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(agent, field, value)

    write_audit_event(
        db,
        principal=principal,
        event_type="agent.updated",
        target_type="agent",
        target_id=agent.id,
        payload={"updated_fields": sorted(updates.keys())},
    )
    db.commit()
    db.refresh(agent)
    return agent


@router.post("/versions", response_model=AgentVersionRead, status_code=status.HTTP_201_CREATED)
def create_agent_version(
    payload: AgentVersionCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> AgentVersion:
    agent = db.get(Agent, payload.agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    # Creating a version is a privileged builder mutation, gated like its siblings
    # (update/validate/publish). The version row does not exist yet, so the denial is
    # audited against the parent agent id (target_type still names the created resource).
    enforce_roles(
        db, principal, PRIVILEGED_ROLES,
        action="agent_version.create", target_type="agent_version", target_id=agent.id,
    )

    # Server assigns the next version number (max+1) so callers can't collide on the
    # (agent_id, version) unique constraint. Any client-supplied version is ignored.
    current_max = db.scalar(
        select(func.max(AgentVersion.version)).where(AgentVersion.agent_id == agent.id)
    )
    next_version = (current_max or 0) + 1

    version = AgentVersion(
        agent_id=agent.id,
        version=next_version,
        status=payload.status,
        config=payload.config,
        created_by=principal.user_id,
    )
    db.add(version)
    db.flush()
    write_audit_event(
        db,
        principal=principal,
        event_type="agent_version.created",
        target_type="agent_version",
        target_id=version.id,
        payload={"agent_id": version.agent_id, "version": version.version},
    )
    db.commit()
    db.refresh(version)
    return version


@router.get("/{agent_id}/versions", response_model=list[AgentVersionRead])
def list_agent_versions(
    agent_id: str,
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> list[AgentVersion]:
    agent = db.get(Agent, agent_id)
    # Same existence-hiding rule as get_agent: an unpublished agent is 404 to non-builders.
    # Scoped to PRIVILEGED_ROLES rather than the literal "admin" (see _is_builder) because
    # validate/publish are: a knowledge-manager that may publish a version but gets 404
    # enumerating that agent's versions holds a capability it cannot start.
    is_builder = _is_builder(principal)
    if agent is None or (not is_builder and agent.status != "published"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    query = (
        select(AgentVersion)
        .where(AgentVersion.agent_id == agent_id)
        .order_by(AgentVersion.version.desc())
    )
    if not is_builder:
        # Even on a published agent, never expose draft/validated (untested) configs.
        query = query.where(AgentVersion.status.in_(("published", "superseded")))
    # Status scoping above is a SQL WHERE (no Python post-filter), so LIMIT/OFFSET can
    # safely live in SQL — the window is computed on the exact set the caller may see
    # (same rationale as list_agents; contrast list_documents' Python-side slicing).
    return list(db.scalars(query.limit(limit).offset(offset)))


@router.post("/versions/{version_id}/validate", response_model=AgentVersionRead)
def validate_agent_version(
    version_id: str,
    payload: AgentVersionValidate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> AgentVersion:
    version = db.get(AgentVersion, version_id)
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent version not found")

    enforce_roles(
        db, principal, PRIVILEGED_ROLES,
        action="agent_version.validate", target_type="agent_version", target_id=version_id,
    )
    version.status = "validated"
    write_audit_event(
        db,
        principal=principal,
        event_type="agent_version.validated",
        target_type="agent_version",
        target_id=version.id,
        reason=payload.reason,
        payload={"agent_id": version.agent_id, "version": version.version},
    )
    db.commit()
    db.refresh(version)
    return version


@router.post("/versions/{version_id}/publish", response_model=AgentVersionRead)
def publish_agent_version(
    version_id: str,
    payload: AgentVersionValidate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> AgentVersion:
    version = db.get(AgentVersion, version_id)
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent version not found")

    enforce_roles(
        db, principal, PRIVILEGED_ROLES,
        action="agent_version.publish", target_type="agent_version", target_id=version_id,
    )
    agent = db.get(Agent, version.agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    published_versions = db.scalars(
        select(AgentVersion).where(
            AgentVersion.agent_id == version.agent_id,
            AgentVersion.status == "published",
        )
    )
    for published_version in published_versions:
        published_version.status = "superseded"

    version.status = "published"
    agent.status = "published"
    write_audit_event(
        db,
        principal=principal,
        event_type="agent_version.published",
        target_type="agent_version",
        target_id=version.id,
        reason=payload.reason,
        payload={"agent_id": version.agent_id, "version": version.version},
    )
    db.commit()
    db.refresh(version)
    return version
