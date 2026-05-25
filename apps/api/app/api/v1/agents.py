from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.principal import Principal, get_principal
from app.domain.model_routing import ModelRoutingPolicyError, normalize_agent_config
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

router = APIRouter()


@router.get("", response_model=list[AgentRead])
def list_agents(db: Session = Depends(get_db)) -> list[Agent]:
    return list(db.scalars(select(Agent).order_by(Agent.created_at.desc())))


@router.get("/{agent_id}", response_model=AgentRead)
def get_agent(agent_id: str, db: Session = Depends(get_db)) -> Agent:
    agent = db.get(Agent, agent_id)
    if agent is None:
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

    version_data = payload.model_dump()
    version_data["config"] = _normalize_config_or_422(version_data["config"])
    version = AgentVersion(**version_data, created_by=principal.user_id)
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
def list_agent_versions(agent_id: str, db: Session = Depends(get_db)) -> list[AgentVersion]:
    agent = db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    return list(
        db.scalars(
            select(AgentVersion)
            .where(AgentVersion.agent_id == agent_id)
            .order_by(AgentVersion.version.desc())
        )
    )


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

    version.config = _normalize_config_or_422(version.config)
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

    agent = db.get(Agent, version.agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    version.config = _normalize_config_or_422(version.config)

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


def _normalize_config_or_422(config: dict) -> dict:
    try:
        return normalize_agent_config(config)
    except ModelRoutingPolicyError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc
