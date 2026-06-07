"""Seed a richer Korean demo dataset for showcasing the full MVP loop.

Creates two knowledge sources with several indexed policy documents and one
published demo agent connected to both. One document is restricted so the
ACL refusal path is demonstrable. Additive — does not touch existing rows.

Run as a module against the real (qdrant-backed) database::

    python -m app.seed_demo_rich
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.principal import Principal
from app.domain.indexing import run_index_job
from app.domain.models import Agent, AgentVersion, Document, IndexJob, KnowledgeSource

_PRINCIPAL = Principal(
    user_id="seed",
    department="Operations",
    roles=("admin",),
    groups=("all-employees",),
    clearance_level="confidential",
)


@dataclass(frozen=True)
class _DemoDoc:
    title: str
    text: str
    confidentiality_level: str = "internal"
    access_groups: tuple[str, ...] = ("all-employees",)


_HR_DOCS = (
    _DemoDoc(
        title="연차·휴가 정책",
        text=(
            "# 연차·휴가 정책\n\n"
            "정규직은 입사 1년 후 연 15일의 연차 유급휴가를 사용할 수 있습니다.\n"
            "1년 미만 재직자는 매월 개근 시 1일의 휴가가 발생합니다.\n\n"
            "## 신청 절차\n\n"
            "휴가는 사용 3일 전까지 관리자 승인을 받아 신청합니다."
        ),
    ),
    _DemoDoc(
        title="재택근무 정책",
        text=(
            "# 재택근무 정책\n\n"
            "전 직원은 주 2일까지 재택근무를 할 수 있습니다.\n"
            "재택근무일에도 핵심 근무시간(10:00-16:00)에는 연락이 가능해야 합니다.\n"
            "보안 문서는 사내망에서만 열람합니다."
        ),
    ),
)

_OPS_DOCS = (
    _DemoDoc(
        title="국내외 출장 규정",
        text=(
            "# 출장 규정\n\n"
            "국내 출장비는 일 5만원, 해외 출장비는 일 10만원을 지급합니다.\n"
            "숙박비는 영수증 실비로 정산하며, 항공권은 이코노미를 원칙으로 합니다."
        ),
    ),
    _DemoDoc(
        title="외부 반출 보안 절차",
        text=(
            "# 외부 반출 보안 절차\n\n"
            "기밀 자료의 외부 반출은 보안팀 사전 승인이 필요합니다.\n"
            "반출 매체는 암호화하고 반출 기록을 90일간 보관합니다."
        ),
        confidentiality_level="restricted",
        access_groups=("department:Operations",),
    ),
)


def _seed_source(db: Session, *, name: str, description: str, owner: str) -> str:
    source = KnowledgeSource(name=name, description=description, owner_department=owner)
    db.add(source)
    db.flush()
    return source.id


def _seed_and_index(db: Session, *, source_id: str, doc: _DemoDoc) -> None:
    document = Document(
        knowledge_source_id=source_id,
        title=doc.title,
        object_uri=f"seed://demo/{doc.title}.md",
        checksum=f"sha256-demo-{doc.title}",
        mime_type="text/markdown",
        confidentiality_level=doc.confidentiality_level,
        access_groups=list(doc.access_groups),
        status="registered",
        effective_date="2026-06-01",
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
            "embedding_model": "bge-m3",
            "force_reindex": False,
            "source": "seed_rich",
        },
        created_by="seed",
    )
    db.add(job)
    db.flush()
    run_index_job(db=db, document=document, job=job, source_text=doc.text, principal=_PRINCIPAL)


def seed_demo_rich(db: Session) -> dict:
    """Seed two sources with indexed docs and one published demo agent.

    Returns a summary dict with created ids and counts.
    """
    hr_source = _seed_source(db, name="인사 정책", description="HR 정책 데모", owner="HR")
    ops_source = _seed_source(db, name="총무·보안", description="총무/보안 데모", owner="Operations")

    for doc in _HR_DOCS:
        _seed_and_index(db, source_id=hr_source, doc=doc)
    for doc in _OPS_DOCS:
        _seed_and_index(db, source_id=ops_source, doc=doc)

    agent = Agent(
        name="사내 도우미(데모)",
        purpose="인사·총무 규정 질의응답 데모",
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
            "knowledge_source_ids": [hr_source, ops_source],
        },
        created_by="seed",
    )
    db.add(version)
    db.flush()
    db.commit()

    return {
        "agent_id": agent.id,
        "knowledge_source_ids": [hr_source, ops_source],
        "document_count": len(_HR_DOCS) + len(_OPS_DOCS),
    }


if __name__ == "__main__":
    from app.core.database import SessionLocal

    with SessionLocal() as session:
        print(seed_demo_rich(session))
