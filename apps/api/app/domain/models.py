import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
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
    # Administrator-configured governance defaults a new Document INHERITS when its own
    # request specifies nothing (WO-2026-08-13-SOURCE-ACL-DEFAULTS). An empty list means NOT
    # CONFIGURED -- the endpoint's own platform fallback then applies, i.e. a source that
    # configures nothing behaves exactly as it did before this column existed.
    #
    # Inheritance is resolved by domain/classification.py, which clamps the confidentiality
    # level UP to the endpoint's fallback and never derives anything from the artifact. This
    # column is NOT consulted by ACL evaluation and NOT part of `list_sources`' clearance
    # filter: a KnowledgeSource still carries no per-source ACL (see list_sources).
    default_access_groups: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
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
    # Durable "this document has, at some point, successfully held trusted indexed
    # content" marker. Set True the first time run_index_job reaches status='indexed'
    # and NEVER reset (not on index_failed, not on archive, not on restore). Unlike the
    # volatile ``status`` field, it survives a document dropping back to 'index_failed'
    # (e.g. a reindex whose vector upsert fails after the unconditional vector purge), so
    # the reindex authorization gate cannot be bypassed through that operational-failure
    # side door. See create_index_job / process_index_job in api/v1/knowledge.py.
    has_been_indexed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Classification PROVENANCE (WO-2026-08-13-SOURCE-ACL-DEFAULTS, SEC-011): where each half
    # of this document's ACL came from, so the population affected by a wrong source default is
    # QUERYABLE as a set instead of being discovered by accident. Values come from
    # domain/classification.py: "explicit" | "source_default" | "platform_default" | "unknown".
    #
    # The two halves are recorded separately on purpose. Confidentiality inheritance is clamped
    # and can only ever RAISE the level, so it cannot widen access; group inheritance is the
    # half that can, which makes "which documents inherited their GROUPS from source X" the
    # exact question an incident needs answered:
    #   SELECT id FROM documents
    #    WHERE access_groups_source = 'source_default' AND classification_source_id = :src;
    #
    # The ORM default is "unknown", never "explicit": a Document built directly through the
    # ORM (seed scripts) records that nobody decided, rather than falsely asserting a choice.
    #
    # HONEST LIMITATION: these are CURRENT-STATE columns, not lineage. A later
    # `PATCH /documents/{id}/acl` overwrites them with "explicit" (correctly -- after a manual
    # relabel the value is no longer inherited), so the historical trail lives in
    # `audit_events`, which records the resolved classification and its provenance for every
    # registration and every ACL change. Append-only per-attempt lineage is
    # `document_ingestions`, a later step in docs/10-architecture/ingestion-normalization-design.md.
    confidentiality_source: Mapped[str] = mapped_column(
        String(40), default="unknown", nullable=False
    )
    access_groups_source: Mapped[str] = mapped_column(String(40), default="unknown", nullable=False)
    #: The knowledge source whose configured defaults were applied, or NULL when nothing was
    #: inherited. Deliberately NOT a foreign key: it is a provenance snapshot of what was
    #: applied, not a live relationship (knowledge_source_id already carries that).
    classification_source_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
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
    #: Append-only ingestion lineage, oldest first. Cascade-deletes only when the DOCUMENT
    #: itself is deleted (the product archives instead, which keeps the whole history).
    ingestions: Mapped[list["DocumentIngestion"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentIngestion.created_at",
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
    ingestions: Mapped[list["DocumentIngestion"]] = relationship(
        back_populates="index_job",
        cascade="all, delete-orphan",
        order_by="DocumentIngestion.created_at",
    )

    @property
    def ingestion(self) -> "DocumentIngestion | None":
        """The lineage this job recorded, for the read model.

        A list underneath a singular accessor on purpose: the table is append-only, so a job
        that somehow ran twice keeps BOTH rows and this returns the latest rather than the
        schema quietly forbidding the second one.
        """
        return self.ingestions[-1] if self.ingestions else None


class DocumentIngestion(Base):
    """APPEND-ONLY lineage: one row per index attempt, never updated, never overwritten.

    WO-2026-08-14-INGESTION-INSTRUMENTATION-001. This is not a column on ``documents`` and
    must not become one. A re-index would overwrite the previous attempt's values, and the
    question a converter defect forces -- "which documents were indexed by the broken version,
    and what did it produce for them?" -- is exactly the question last-write-wins destroys.
    Same reasoning as ``documents.has_been_indexed`` (0005): the durable record and the
    volatile current state are different facts and need different storage.

    NULL means NOT OBSERVED and is distinct from 0. A row with ``chunk_count = 0`` says the
    attempt produced no chunks; a row with ``chunk_count = NULL`` says nobody counted. The
    backfill relies on that distinction (see 0007), and so does anyone aggregating these rows:
    averaging NULLs as zeroes would invent data.

    NOTHING HERE IS A QUALITY SCORE. Every column is a count, an identifier, or a warning code
    derived from counts. See app/domain/ingestion_lineage.py for the derivation and for why
    the low-density threshold is a flag for a human rather than a verdict.
    """

    __tablename__ = "document_ingestions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id"), nullable=False, index=True
    )
    #: The attempt this row describes. NULL only for backfilled rows, where the attempt that
    #: produced the existing chunks genuinely cannot be identified: a non-force re-index leaves
    #: earlier chunk rows in place, so the current chunk set can span several jobs.
    index_job_id: Mapped[str | None] = mapped_column(
        ForeignKey("index_jobs.id"), nullable=True, index=True
    )
    #: ``ok`` | ``failed`` | ``unknown`` -- see app/domain/ingestion_lineage.py. ``unknown`` is
    #: reserved for rows nobody observed; live code never writes it.
    extraction_status: Mapped[str] = mapped_column(String(20), nullable=False)
    #: The document's declared MIME type, i.e. what the uploader said it was.
    source_mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    #: WHAT THE CHUNKER ACTUALLY SAW. Today this is always ``text/plain`` for PDF and DOCX,
    #: which is the point: this single column makes the citation collapse queryable.
    converted_mime_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    #: Extractor and version plus the chunker's input type, e.g. ``pypdf/6.14.2>text/plain``.
    converter_chain: Mapped[str | None] = mapped_column(String(240), nullable=True)
    chunk_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: How many chunks carried a NON-EMPTY section_path. The most important number here: its
    #: ratio to chunk_count is how much of the document's structure reached the citation.
    structured_chunk_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extracted_char_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: ``page`` | ``paragraph`` | ``line`` -- the unit source_unit_count counts.
    source_unit_kind: Mapped[str | None] = mapped_column(String(20), nullable=True)
    source_unit_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    document: Mapped[Document] = relationship(back_populates="ingestions")
    index_job: Mapped[IndexJob | None] = relationship(back_populates="ingestions")


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
    chunk_id: Mapped[str | None] = mapped_column(
        ForeignKey("document_chunks.id"), nullable=True
    )
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
    """A persisted eval-harness run: the full aggregate report plus headline metadata.

    The report shape is intentionally unnormalized (JSON blob) — the eval harness's
    aggregate() output evolves faster than a relational schema should.
    """

    __tablename__ = "eval_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    corpus_id: Mapped[str] = mapped_column(String(120), nullable=False)
    created_by: Mapped[str] = mapped_column(String(120), nullable=False)
    label: Mapped[str | None] = mapped_column(String(240), nullable=True)
    report: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


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
