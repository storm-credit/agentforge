from __future__ import annotations

import logging
from datetime import UTC, datetime
from time import perf_counter

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.database import get_db
from app.core.principal import Principal, get_principal
from app.domain.citations import CitationValidationResult, validate_run_citations
from app.domain.grounding import grounding_score
from app.domain.input_guard import assess_input
from app.domain.models import Agent, AgentVersion, Document, DocumentChunk, RetrievalHit, Run, RunStep
from app.domain.schemas import (
    RetrievalHitRead,
    RunCreate,
    RunRead,
    RunStepRead,
)
from app.domain.language import resolve_language
from app.domain.pii import mask_pii
from app.domain.vector import FakeVectorStore, VectorQuery, VectorSearchResult, build_acl_filter, get_vector_store
from app.infra.audit import write_audit_event
from app.services.llm_gateway import ContextBlock, clamp_temperature, clamp_top_p, get_gateway
from app.services.answerability_judge import get_judge
from app.services.reranker import get_reranker

logger = logging.getLogger(__name__)

router = APIRouter()


def _hit_locator(hit) -> str | None:
    return hit.citation_locator or hit.citation


def _guard_refusal(language: str) -> str:
    if language == "en":
        return "I can't answer this from the available documents."
    return "근거가 부족하여 답변할 수 없습니다."


def _can_read_run(principal: Principal, run: Run) -> bool:
    """A run's answer/trace is readable by its owner or an admin/operator.

    Header-stub identity for now (SSO not wired) — but this still enforces that one
    user cannot read another user's run output via the GET endpoints.
    """
    return run.user_id == principal.user_id or "admin" in principal.roles


@router.get("", response_model=list[RunRead])
def list_runs(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> list[Run]:
    statement = select(Run).order_by(Run.created_at.desc())
    if "admin" not in principal.roles:
        statement = statement.where(Run.user_id == principal.user_id)
    return list(db.scalars(statement))


@router.post("", response_model=RunRead, status_code=status.HTTP_201_CREATED)
def create_run(
    payload: RunCreate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> Run:
    agent = db.get(Agent, payload.agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    agent_version = _resolve_agent_version(db, agent, payload.agent_version_id)
    knowledge_source_ids = _runtime_knowledge_sources(payload, agent_version)
    acl_filter = build_acl_filter(principal)
    started_at = datetime.now(UTC)
    timer_start = perf_counter()

    run = Run(
        agent_id=agent.id,
        agent_version_id=agent_version.id,
        user_id=principal.user_id,
        user_department=principal.department,
        status="running",
        input={
            **payload.input.model_dump(),
            "mode": payload.mode,
            "debug": payload.debug,
            "knowledge_source_ids": knowledge_source_ids,
            "top_k": payload.top_k,
        },
        started_at=started_at,
    )
    db.add(run)
    db.flush()

    # Input guard: deterministic, non-model heuristic (control chars + a short,
    # best-effort prompt-injection marker list). Log-not-block by design — it
    # never refuses the run (false positives on legitimate questions), it only
    # makes the trace/audit honest about what was checked. Real injection
    # robustness needs the in-house LLM and is out of scope here.
    guard_input = assess_input(payload.input.message)
    _add_step(
        db,
        run=run,
        order=1,
        step_type="guard_input",
        input_summary={"message_length": len(payload.input.message)},
        output_summary={
            "allowed": True,  # heuristic logs, never blocks
            "risk_level": guard_input.risk_level,
            "markers": list(guard_input.markers),
        },
        started_at=started_at,
    )
    if guard_input.risk_level != "low":
        # Marker labels + risk level only — the raw (attacker-controlled) message
        # is deliberately NOT copied into the audit payload/reason.
        write_audit_event(
            db,
            principal=principal,
            event_type="run.input_guard.injection_detected",
            target_type="run",
            target_id=run.id,
            reason=f"input guard heuristic flagged risk={guard_input.risk_level}",
            payload={
                "risk_level": guard_input.risk_level,
                "markers": list(guard_input.markers),
            },
        )

    vector_result, vector_adapter, vector_degraded = _search_authorized_context(
        db=db,
        query_text=payload.input.message,
        knowledge_source_ids=knowledge_source_ids,
        top_k=payload.top_k,
        acl_filter=acl_filter,
    )
    # Rerank hook: order-preserving no-op by default. Chunk content is fetched here
    # (VectorHit carries no content) so content-aware backends (hybrid_lexical BM25)
    # can score against the actual chunk text; the same map is reused for context
    # blocks below, so this is a single DB round-trip either way.
    content_by_chunk_id = _fetch_chunk_contents(db, vector_result.hits)
    rank_before_rerank = {hit: rank for rank, hit in enumerate(vector_result.hits, start=1)}
    reranker = get_reranker()
    ranked_hits = reranker.rerank(payload.input.message, vector_result.hits, content_by_chunk_id)
    _add_step(
        db,
        run=run,
        order=2,
        step_type="retriever",
        input_summary={
            "query_length": len(payload.input.message),
            "knowledge_source_count": len(knowledge_source_ids),
            "top_k": payload.top_k,
        },
        output_summary={
            "hit_count": len(ranked_hits),
            "denied_count": vector_result.denied_count,
            "vector_adapter": vector_adapter,
            "degraded": vector_degraded,
            "reranker": reranker.name,
        },
    )

    citations = []
    for rank, hit in enumerate(ranked_hits, start=1):
        citation_locator = _hit_locator(hit)
        usable_as_citation = bool(hit.chunk_id and citation_locator)
        db.add(
            RetrievalHit(
                run_id=run.id,
                chunk_id=hit.chunk_id,
                document_id=hit.document_id,
                title=hit.title,
                citation_locator=citation_locator,
                rank_original=rank_before_rerank.get(hit, rank),
                rank_reranked=rank,
                score_vector=hit.score,
                score_rerank=None,
                used_in_context=True,
                used_as_citation=usable_as_citation,
                acl_filter_snapshot={
                    "subjects": list(acl_filter.subjects),
                    "clearance_level": acl_filter.clearance_level,
                    "knowledge_source_ids": knowledge_source_ids,
                    "vector_adapter": vector_adapter,
                },
            )
        )
        if usable_as_citation:
            citations.append(
                {
                    "document_id": hit.document_id,
                    "chunk_id": hit.chunk_id,
                    "title": hit.title,
                    "citation_locator": citation_locator,
                    "score": hit.score,
                }
            )

    answer_language = resolve_language(payload.language, payload.input.message)
    context_blocks = _build_context_blocks(ranked_hits, content_by_chunk_id)
    gen_settings = get_settings()
    gen_temperature = clamp_temperature(
        agent_version.config.get("temperature", gen_settings.llm_temperature)
    )
    gen_top_p = clamp_top_p(agent_version.config.get("top_p", gen_settings.llm_top_p))

    # Answer-confidence gate (refusal discipline): if the best retrieval score is below
    # answer_min_score, the retrieved context is too weak to answer on — refuse instead of
    # answering from a loosely-related accessible document. Separate from retrieval_min_score
    # (which controls what enters context). Default 0.0 = off (no behaviour change).
    top_score = max((hit.score for hit in vector_result.hits), default=0.0)
    confidence_ok = top_score >= gen_settings.answer_min_score
    grounding = None
    guard_tripped = False
    confidence_gate_tripped = not confidence_ok

    # LLM-as-judge answerability gate: even when the scalar confidence gate passes, a
    # semantic judge can catch accessible-but-irrelevant context (the over-answer case
    # scalar scores miss). Default no-op; runs on the local LLM when enabled.
    judge = get_judge()
    judge_refused = False
    if confidence_ok and context_blocks and judge.name != "none":
        judge_refused = not judge.is_answerable(payload.input.message, context_blocks)

    if confidence_gate_tripped or judge_refused:
        run.answer = _guard_refusal(answer_language)
        citations = []
        run.citations = citations
        run.retrieval_denied_count = vector_result.denied_count

        class _Refused:
            used_llm = False
            fallback_used = False

        generated = _Refused()
    else:
        generated = get_gateway().generate(
            question=payload.input.message,
            context=context_blocks,
            language=answer_language,
            temperature=gen_temperature,
            top_p=gen_top_p,
        )
        run.answer = generated.text
        run.citations = citations
        run.retrieval_denied_count = vector_result.denied_count

        # Output guard: an LLM answer that is not grounded in the retrieved context
        # (e.g. a prompt-injection hijack) is replaced with a safe refusal.
        if generated.used_llm and context_blocks:
            grounding = grounding_score(
                run.answer, "\n".join(block.content for block in context_blocks)
            )
            if grounding < gen_settings.grounding_min:
                guard_tripped = True
                run.answer = _guard_refusal(answer_language)
                citations = []
                run.citations = citations

    # PII masking (defense-in-depth, opt-in): redact known PII patterns from the
    # final answer before it is persisted/returned. Regex-based and conservative —
    # deterministic but not exhaustive (natural-language PII is not caught).
    pii_masked = False
    if gen_settings.pii_masking_enabled:
        run.answer, pii_masked = mask_pii(run.answer)
        # Citation title/locator are derived from document headings and can carry the
        # same PII — mask them too, or the redaction leaks through a sibling field.
        masked_citations = []
        for citation in citations:
            title, title_changed = mask_pii(citation.get("title"))
            locator, locator_changed = mask_pii(citation.get("citation_locator"))
            pii_masked = pii_masked or title_changed or locator_changed
            masked_citations.append({**citation, "title": title, "citation_locator": locator})
        citations = masked_citations
        run.citations = citations

    citation_required = bool(agent_version.config.get("citation_required", True))
    citation_validation = validate_run_citations(
        citations,
        citation_required=citation_required,
    )
    run.guardrail = {
        "acl_filter_applied": True,
        "citation_required": citation_required,
        "citation_count": len(citations),
        "citation_validation_pass": citation_validation.passed,
        "citation_validation_error_code": citation_validation.error_code,
        "citation_validation_missing_fields": list(citation_validation.missing_fields),
        "pii_masked": pii_masked,
        "security_finalcheck_pass": citation_validation.passed,
    }

    _add_step(
        db,
        run=run,
        order=3,
        step_type="generator",
        input_summary={"context_count": len(context_blocks)},
        output_summary={
            "answer_length": len(run.answer),
            "citation_count": len(citations),
            "mode": "llm" if generated.used_llm else ("fallback" if generated.fallback_used else "refused"),
            "language": answer_language,
            "temperature": gen_temperature,
            "top_p": gen_top_p,
        },
    )
    _add_step(
        db,
        run=run,
        order=4,
        step_type="citation_validator",
        input_summary={
            "citation_required": citation_validation.required,
            "citation_count": citation_validation.citation_count,
        },
        output_summary=_citation_validation_summary(citation_validation),
        status="succeeded" if citation_validation.passed else "failed",
        error_code=citation_validation.error_code,
        error_message=citation_validation.error_message,
    )
    _add_step(
        db,
        run=run,
        order=5,
        step_type="guard_output",
        input_summary={"answer_length": len(run.answer)},
        output_summary={
            "security_finalcheck_pass": citation_validation.passed,
            "citation_count": len(citations),
            "grounding_score": grounding,
            "guard_tripped": guard_tripped,
            "top_score": round(top_score, 4),
            "confidence_gate_tripped": confidence_gate_tripped,
            "judge": judge.name,
            "judge_refused": judge_refused,
        },
        status="succeeded" if citation_validation.passed else "failed",
        error_code=citation_validation.error_code,
        error_message=citation_validation.error_message,
    )

    run.status = "succeeded" if citation_validation.passed else "failed"
    run.finished_at = datetime.now(UTC)
    run.latency_ms = max(1, int((perf_counter() - timer_start) * 1000))
    write_audit_event(
        db,
        principal=principal,
        event_type="run.created",
        target_type="run",
        target_id=run.id,
        payload={
            "agent_id": run.agent_id,
            "agent_version_id": run.agent_version_id,
            "status": run.status,
            "query_length": len(payload.input.message),
            "retrieval_hit_count": len(vector_result.hits),
            "citation_count": len(citations),
            "retrieval_denied_count": vector_result.denied_count,
            "citation_validation_pass": citation_validation.passed,
            "citation_validation_error_code": citation_validation.error_code,
            "step_count": 5,
        },
    )
    db.commit()
    db.refresh(run)
    return run


@router.get("/{run_id}", response_model=RunRead)
def get_run(
    run_id: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> Run:
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    if not _can_read_run(principal, run):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this run")
    return run


@router.get("/{run_id}/steps", response_model=list[RunStepRead])
def list_run_steps(
    run_id: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> list[RunStep]:
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    if not _can_read_run(principal, run):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this run")

    return list(
        db.scalars(
            select(RunStep).where(RunStep.run_id == run_id).order_by(RunStep.step_order)
        )
    )


@router.get("/{run_id}/retrieval-hits", response_model=list[RetrievalHitRead])
def list_run_retrieval_hits(
    run_id: str,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> list[RetrievalHitRead]:
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    if not _can_read_run(principal, run):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this run")

    hits = list(
        db.scalars(
            select(RetrievalHit)
            .where(RetrievalHit.run_id == run_id)
            .order_by(RetrievalHit.rank_original)
        )
    )
    chunk_ids = [hit.chunk_id for hit in hits if hit.chunk_id]
    contents: dict[str, str] = {}
    if chunk_ids:
        rows = db.scalars(select(DocumentChunk).where(DocumentChunk.id.in_(chunk_ids)))
        contents = {row.id: row.content for row in rows}
    mask_enabled = get_settings().pii_masking_enabled

    def _read(hit: RetrievalHit) -> RetrievalHitRead:
        content = contents.get(hit.chunk_id or "")
        update: dict = {"content": content}
        if mask_enabled:
            # Mask content AND the title/locator (heading-derived) so PII does not
            # leak through a sibling field while content is redacted.
            update["content"] = mask_pii(content)[0] if content else content
            update["title"] = mask_pii(hit.title)[0]
            update["citation_locator"] = mask_pii(hit.citation_locator)[0]
        return RetrievalHitRead.model_validate(hit).model_copy(update=update)

    return [_read(hit) for hit in hits]


def _resolve_agent_version(
    db: Session,
    agent: Agent,
    agent_version_id: str | None,
) -> AgentVersion:
    if agent_version_id is not None:
        version = db.get(AgentVersion, agent_version_id)
        if version is None or version.agent_id != agent.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent version not found",
            )
        if version.status != "published":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Agent version is not published",
            )
        return version

    version = db.scalar(
        select(AgentVersion)
        .where(AgentVersion.agent_id == agent.id, AgentVersion.status == "published")
        .order_by(AgentVersion.version.desc())
    )
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Published agent version not found",
        )
    return version


def _runtime_knowledge_sources(payload: RunCreate, agent_version: AgentVersion) -> list[str]:
    if payload.knowledge_source_ids:
        return payload.knowledge_source_ids

    configured = agent_version.config.get("knowledge_source_ids", [])
    if not isinstance(configured, list):
        return []

    return [source_id for source_id in configured if isinstance(source_id, str)]


def _search_authorized_context(
    *,
    db: Session,
    query_text: str,
    knowledge_source_ids: list[str],
    top_k: int,
    acl_filter,
) -> tuple[VectorSearchResult, str, bool]:
    documents = list(
        db.scalars(
            select(Document)
            .options(selectinload(Document.chunks))
            .order_by(Document.created_at.desc())
        )
    )
    query = VectorQuery(
        query_text=query_text,
        knowledge_source_ids=tuple(knowledge_source_ids),
        top_k=top_k,
        min_score=get_settings().retrieval_min_score,
    )
    store = get_vector_store()
    label = "fake" if isinstance(store, FakeVectorStore) else "qdrant"
    try:
        result = store.search(query=query, documents=documents, acl_filter=acl_filter)
        return result, label, False
    except Exception as exc:  # noqa: BLE001 - stay answerable, ACL-safe, but mark degraded
        logger.warning("vector search failed (%s); falling back to FakeVectorStore", exc)
        result = FakeVectorStore().search(query=query, documents=documents, acl_filter=acl_filter)
        return result, "fake_fallback", True


def _add_step(
    db: Session,
    *,
    run: Run,
    order: int,
    step_type: str,
    input_summary: dict,
    output_summary: dict,
    started_at: datetime | None = None,
    status: str = "succeeded",
    error_code: str | None = None,
    error_message: str | None = None,
) -> None:
    step_started_at = started_at or datetime.now(UTC)
    step_finished_at = datetime.now(UTC)
    latency_ms = max(1, int((step_finished_at - step_started_at).total_seconds() * 1000))
    db.add(
        RunStep(
            run_id=run.id,
            step_order=order,
            step_type=step_type,
            status=status,
            input_summary=input_summary,
            output_summary=output_summary,
            started_at=step_started_at,
            finished_at=step_finished_at,
            latency_ms=latency_ms,
            error_code=error_code,
            error_message=error_message,
        )
    )


def _citation_validation_summary(result: CitationValidationResult) -> dict:
    return {
        "passed": result.passed,
        "required": result.required,
        "citation_count": result.citation_count,
        "error_code": result.error_code,
        "missing_fields": list(result.missing_fields),
    }


def _fetch_chunk_contents(db: Session, hits) -> dict[str, str]:
    """chunk_id -> content for the given hits (single query; fetched once per run,
    shared by the reranker and the context-block builder)."""
    chunk_ids = [hit.chunk_id for hit in hits if hit.chunk_id]
    if not chunk_ids:
        return {}
    rows = db.scalars(select(DocumentChunk).where(DocumentChunk.id.in_(chunk_ids)))
    return {row.id: row.content for row in rows}


def _build_context_blocks(hits, contents: dict[str, str]) -> tuple[ContextBlock, ...]:
    blocks = []
    for hit in hits:
        text = contents.get(hit.chunk_id or "", "")
        if not text:
            continue
        blocks.append(ContextBlock(title=hit.title, locator=_hit_locator(hit), content=text))
    return tuple(blocks)
