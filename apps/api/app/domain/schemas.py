from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    purpose: str = Field(min_length=1)
    owner_department: str = Field(min_length=1, max_length=120)
    status: str = "draft"


class AgentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    purpose: str | None = Field(default=None, min_length=1)
    owner_department: str | None = Field(default=None, min_length=1, max_length=120)
    status: str | None = None


class AgentRead(BaseModel):
    id: str
    name: str
    purpose: str
    owner_department: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentVersionCreate(BaseModel):
    agent_id: str
    version: int = Field(ge=1)
    status: str = "draft"
    config: dict[str, Any] = Field(default_factory=dict)


class AgentVersionValidate(BaseModel):
    reason: str = "Sprint 0 metadata validation"


class AgentVersionRead(BaseModel):
    id: str
    agent_id: str
    version: int
    status: str
    config: dict[str, Any]
    created_by: str
    created_at: datetime
    published_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class KnowledgeSourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = ""
    owner_department: str = Field(min_length=1, max_length=120)
    default_confidentiality_level: str = "internal"
    status: str = "active"


class KnowledgeSourceRead(BaseModel):
    id: str
    name: str
    description: str
    owner_department: str
    default_confidentiality_level: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentCreate(BaseModel):
    knowledge_source_id: str
    title: str = Field(min_length=1, max_length=240)
    object_uri: str = Field(min_length=1, max_length=500)
    checksum: str = Field(min_length=1, max_length=128)
    mime_type: str = Field(min_length=1, max_length=120)
    confidentiality_level: str = "internal"
    access_groups: list[str] = Field(default_factory=list)
    status: str = "registered"
    effective_date: str | None = None


class DocumentRead(BaseModel):
    id: str
    knowledge_source_id: str
    title: str
    object_uri: str
    checksum: str
    mime_type: str
    confidentiality_level: str
    access_groups: list[str]
    status: str
    effective_date: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RetrievalPreviewRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    knowledge_source_ids: list[str] = Field(default_factory=list)
    top_k: int = Field(default=5, ge=1, le=20)


class RetrievalPreviewHit(BaseModel):
    document_id: str
    knowledge_source_id: str
    title: str
    confidentiality_level: str
    access_groups: list[str]
    score: float
    citation: str


class RetrievalPreviewResponse(BaseModel):
    query: str
    hits: list[RetrievalPreviewHit]
    denied_count: int
