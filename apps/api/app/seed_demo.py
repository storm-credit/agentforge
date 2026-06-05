"""Seed one published demo agent and one indexed policy document.

Run as a module to seed the real database::

    python -m app.seed_demo
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.principal import Principal
from app.domain.indexing import run_index_job
from app.domain.models import Agent, AgentVersion, Document, IndexJob, KnowledgeSource

_PRINCIPAL = Principal(
    user_id="seed",
    department="Operations",
    roles=("admin",),
    groups=("all-employees",),
    clearance_level="internal",
)

_SAMPLE = (
    "# 휴가 정책\n\n"
    "전 직원은 연 5일의 유급 휴가를 사용할 수 있습니다.\n\n"
    "## 신청\n\n"
    "관리자 승인 후 사용합니다."
)


def seed_demo(db: Session) -> dict:
    """Create a demo agent (published) and index a sample policy document.

    Returns a dict with ``agent_id``, ``agent_version_id``, ``source_id``,
    and ``chunk_count`` so callers can surface seed results.
    """
    source = KnowledgeSource(
        name="사내 정책",
        description="데모",
        owner_department="Operations",
    )
    db.add(source)
    db.flush()

    agent = Agent(
        name="사내 도우미",
        purpose="사내 문서 질의응답",
        owner_department="Operations",
        status="published",
    )
    db.add(agent)
    db.flush()

    version = AgentVersion(
        agent_id=agent.id,
        version=1,
        status="published",
        config={
            "citation_required": True,
            "knowledge_source_ids": [source.id],
        },
        created_by="seed",
    )
    db.add(version)
    db.flush()

    document = Document(
        knowledge_source_id=source.id,
        title="휴가 정책",
        object_uri="object://seed/holiday.md",
        checksum="sha256-seed",
        mime_type="text/markdown",
        confidentiality_level="internal",
        access_groups=["all-employees"],
        status="registered",
        effective_date="2026-05-10",
    )
    db.add(document)
    db.flush()

    job = IndexJob(
        document_id=document.id,
        status="queued",
        stage="parse",
        config={
            "parser_profile": "default-txt-md",
            "chunking": {"chunk_size": 900},
            "embedding_model": "none-smoke",
            "force_reindex": False,
            "source": "seed",
        },
        created_by="seed",
    )
    db.add(job)
    db.flush()

    run_index_job(db=db, document=document, job=job, source_text=_SAMPLE, principal=_PRINCIPAL)
    db.commit()

    return {
        "agent_id": agent.id,
        "agent_version_id": version.id,
        "source_id": source.id,
        "chunk_count": job.chunk_count,
    }


if __name__ == "__main__":
    from app.core.database import SessionLocal

    with SessionLocal() as session:
        print(seed_demo(session))
