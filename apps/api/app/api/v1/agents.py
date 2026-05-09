from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.principal import Principal, get_principal
from app.domain.models import Agent, AgentVersion
from app.domain.schemas import AgentCreate, AgentRead, AgentVersionCreate, AgentVersionRead
from app.infra.audit import write_audit_event

router = APIRouter()


@router.get("", response_model=list[AgentRead])
def list_agents(db: Session = Depends(get_db)) -> list[Agent]:
    return list(db.scalars(select(Agent).order_by(Agent.created_at.desc())))


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


@router.post("/versions", response_model=AgentVersionRead, status_code=status.HTTP_201_CREATED)
def create_agent_version(
    payload: AgentVersionCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> AgentVersion:
    agent = db.get(Agent, payload.agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    version = AgentVersion(**payload.model_dump(), created_by=principal.user_id)
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

