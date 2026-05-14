import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC)


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    owner_department: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="draft", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    versions: Mapped[list["AgentVersion"]] = relationship(
        back_populates="agent", cascade="all, delete-orphan"
    )
    runs: Mapped[list["Run"]] = relationship(back_populates="agent", cascade="all, delete-orphan")


class AgentVersion(Base):
    __tablename__ = "agent_versions"
    __table_args__ = (UniqueConstraint("agent_id", "version", name="uq_agent_versions_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="draft", nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_by: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    agent: Mapped[Agent] = relationship(back_populates="versions")
    runs: Mapped[list["Run"]] = relationship(
        back_populates="agent_version", cascade="all, delete-orphan"
    )


class KnowledgeSource(Base):
    __tablename__ = "knowledge_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    owner_department: Mapped[str] = mapped_column(String(120), nullable=False)
    default_confidentiality_level: Mapped[str] = mapped_column(
        String(40), default="internal", nullable=False
    )
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    documents: Mapped[list["Document"]] = relationship(
        back_populates="knowledge_source", cascade="all, delete-orphan"
    )


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    knowledge_source_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_sources.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    object_uri: Mapped[str] = mapped_column(String(500), nullable=False)
    checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    confidentiality_level: Mapped[str] = mapped_column(String(40), nullable=False)
    access_groups: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="registered", nullable=False)
    effective_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    knowledge_source: Mapped[KnowledgeSource] = relationship(back_populates="documents")
    index_jobs: Mapped[list["IndexJob"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentChunk.chunk_index",
    )


class IndexJob(Base):
    __tablename__ = "index_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="queued", nullable=False)
    stage: Mapped[str] = mapped_column(String(40), default="parse", nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_by: Mapped[str] = mapped_column(String(120), nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    artifact_uri: Mapped[str | None] = mapped_column(String(500), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    document: Mapped[Document] = relationship(back_populates="index_jobs")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(String(220), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    chunk_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    line_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    line_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_path: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    citation_locator: Mapped[str] = mapped_column(String(300), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(80), nullable=False)
    chunker_version: Mapped[str] = mapped_column(String(80), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(120), nullable=False)
    vector_ref: Mapped[str] = mapped_column(String(240), nullable=False)
    acl_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="indexed", nullable=False)
    indexed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    document: Mapped[Document] = relationship(back_populates="chunks")
    retrieval_hits: Mapped[list["RetrievalHit"]] = relationship(back_populates="chunk")


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False)
    agent_version_id: Mapped[str] = mapped_column(ForeignKey("agent_versions.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(120), nullable=False)
    user_department: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="queued", nullable=False)
    input: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    answer: Mapped[str] = mapped_column(Text, default="", nullable=False)
    citations: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    guardrail: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    retrieval_denied_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    agent: Mapped[Agent] = relationship(back_populates="runs")
    agent_version: Mapped[AgentVersion] = relationship(back_populates="runs")
    steps: Mapped[list["RunStep"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="RunStep.step_order"
    )
    retrieval_hits: Mapped[list["RetrievalHit"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="RetrievalHit.rank_original"
    )


class RunStep(Base):
    __tablename__ = "run_steps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), nullable=False)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="started", nullable=False)
    input_summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    output_summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    run: Mapped[Run] = relationship(back_populates="steps")


class RetrievalHit(Base):
    __tablename__ = "retrieval_hits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), nullable=False)
    chunk_id: Mapped[str | None] = mapped_column(ForeignKey("document_chunks.id"), nullable=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    citation_locator: Mapped[str | None] = mapped_column(String(300), nullable=True)
    rank_original: Mapped[int] = mapped_column(Integer, nullable=False)
    rank_reranked: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_vector: Mapped[float] = mapped_column(Float, nullable=False)
    score_rerank: Mapped[float | None] = mapped_column(Float, nullable=True)
    used_in_context: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    used_as_citation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    acl_filter_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    run: Mapped[Run] = relationship(back_populates="retrieval_hits")
    chunk: Mapped[DocumentChunk | None] = relationship(back_populates="retrieval_hits")


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    corpus_id: Mapped[str] = mapped_column(String(120), nullable=False)
    mode: Mapped[str] = mapped_column(String(40), default="api", nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    total_cases: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    passed_cases: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_cases: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    suite_counts: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    setup_findings: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    setup: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    model_routing_policy_ref: Mapped[str] = mapped_column(String(240), default="", nullable=False)
    budget_class: Mapped[str] = mapped_column(String(40), default="standard", nullable=False)
    model_route_summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_by: Mapped[str] = mapped_column(String(120), nullable=False)
    approved_baseline_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    approved_baseline_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    results: Mapped[list["EvalCaseResult"]] = relationship(
        back_populates="eval_run", cascade="all, delete-orphan", order_by="EvalCaseResult.case_id"
    )


class EvalCaseResult(Base):
    __tablename__ = "eval_case_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    eval_run_id: Mapped[str] = mapped_column(ForeignKey("eval_runs.id"), nullable=False)
    case_id: Mapped[str] = mapped_column(String(120), nullable=False)
    suite: Mapped[str] = mapped_column(String(80), nullable=False)
    expected_behavior: Mapped[str] = mapped_column(String(80), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    findings: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    citation_document_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    retrieval_document_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    retrieval_denied_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    eval_run: Mapped[EvalRun] = relationship(back_populates="results")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(120), nullable=False)
    actor_department: Mapped[str] = mapped_column(String(120), nullable=False)
    target_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[str] = mapped_column(String(120), nullable=False)
    reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
