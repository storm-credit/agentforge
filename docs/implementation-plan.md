# Agent Forge Implementation Plan

## 1. 범위

MVP는 폐쇄망 내부 문서 기반 RAG Agent Builder다. 기술 기준은 FastAPI, Next.js, PostgreSQL, Qdrant 또는 pgvector, MinIO, vLLM/로컬 모델 서빙이다.

MVP included:

- Agent Registry와 version/publish 흐름
- Knowledge Source와 문서 업로드/인덱싱
- ACL-aware retrieval
- citation 기반 답변
- Runtime run/run_step/retrieval/audit 로그
- Agent Studio 최소 운영 화면
- 폐쇄망 offline package와 기본 observability
- QA/Eval golden set 회귀 실행

MVP excluded:

- ERP write action
- groupware/email 자동화
- 완전 자율 multi-agent
- confidential 문서 자동 처리. 기본은 제외 또는 명시 승인
- 복잡한 승인 workflow. publish approval 구조만 준비

## 2. 시스템 구성

```text
User/Admin
  -> Next.js Agent Studio
  -> FastAPI Control/Runtime API
    -> PostgreSQL
    -> MinIO
    -> Qdrant 또는 PostgreSQL pgvector
    -> Model Gateway
      -> vLLM Chat Model
      -> Embedding Model
      -> Reranker(optional)
```

서비스 분리:

- `web`: Next.js Agent Studio
- `api`: FastAPI API server
- `worker-indexing`: document parse/chunk/embed/index worker
- `worker-eval`: regression/eval runner
- `postgres`: metadata/audit/eval DB
- `qdrant` 또는 `pgvector`: vector index
- `minio`: raw documents/artifacts
- `model-gateway`: backend client layer 또는 별도 service

## 3. Repository Layout 제안

```text
apps/
  api/
    app/
      api/v1/
      core/
      domain/
      infra/
      workers/
      tests/
    alembic/
    pyproject.toml
  web/
    app/
    components/
    features/
    lib/
    tests/
packages/
  shared-contracts/
deploy/
  compose/
  helm/
  offline/
docs/
  implementation-plan.md
  evaluation-plan.md
```

공통 contract는 OpenAPI schema에서 생성하거나, 최소한 API request/response fixture를 `shared-contracts`에 둔다.

## 4. Backend 구현 계획

상세 API와 DB 초안은 다음 문서를 기준으로 한다.

- `notes/06_Backend/API 초안.md`
- `notes/06_Backend/DB 테이블 초안.md`

### 4.1 Foundation

작업:

- FastAPI app skeleton
- settings loader: env, `.env`, 폐쇄망 secret mount
- structured JSON logging
- problem response exception handler
- request id/trace id middleware
- auth principal dependency
- SQLAlchemy/Alembic setup
- repository/service layer convention

완료 조건:

- `/healthz`, `/readyz` 동작
- DB 연결 실패 시 `/readyz`가 실패를 반환
- OpenAPI 문서가 생성되고 contract test에서 schema load 가능

### 4.2 Database Migration

우선 migration:

1. `agents`, `agent_versions`
2. `knowledge_sources`, `documents`, `document_acl`, `index_jobs`
3. `document_chunks`, vector adapter metadata
4. `runs`, `run_steps`, `retrieval_hits`, `audit_events`
5. `eval_cases`, `eval_runs`, `eval_results`
6. `tools`, `tool_permissions`, `approvals`, `system_settings`

완료 조건:

- fresh DB migration 성공
- migration downgrade 또는 forward-fix 전략 문서화
- seed script로 dev admin, sample source, sample agent 생성 가능

### 4.3 Agent Registry

구현 API:

- `GET /api/v1/agents`
- `POST /api/v1/agents`
- `GET /api/v1/agents/{agent_id}`
- `PATCH /api/v1/agents/{agent_id}`
- `POST /api/v1/agents/{agent_id}/versions`
- `PATCH /api/v1/agents/{agent_id}/versions/{version_id}`
- `POST /api/v1/agents/{agent_id}/versions/{version_id}/validate`
- `POST /api/v1/agents/{agent_id}/versions/{version_id}/publish`

핵심 로직:

- draft/validated/published/superseded 상태 전이
- published version 단일성 보장
- retrieval/model/policy config schema validation
- publish 시 audit event 기록

완료 조건:

- 동시에 publish 요청이 들어와도 published version이 하나만 남는다.
- invalid config는 validation 단계에서 구체적인 field error로 반환된다.

### 4.4 Knowledge / Document Ingestion

구현 API:

- `GET/POST /api/v1/knowledge-sources`
- `GET/PATCH /api/v1/knowledge-sources/{source_id}`
- `POST /api/v1/documents`
- `GET/PATCH /api/v1/documents/{document_id}`
- `POST /api/v1/documents/{document_id}/index-jobs`
- `GET /api/v1/index-jobs/{job_id}`
- `GET /api/v1/documents/{document_id}/chunks`

Worker pipeline:

1. MinIO 원본 저장
2. MIME/checksum 검증
3. parser 실행
4. text normalization
5. chunking
6. chunk metadata 저장
7. embedding 생성
8. Qdrant/pgvector upsert
9. index job 완료/audit event

완료 조건:

- PDF/DOCX/TXT/MD smoke fixture 인덱싱 성공
- 실패 job은 stage/error_code/error_message를 남긴다.
- 문서 revoke 후 검색 결과에서 제외된다.

### 4.5 Vector Adapter

공통 인터페이스:

```python
class VectorStore:
    async def upsert_chunks(self, chunks: list[ChunkEmbedding]) -> None: ...
    async def search(self, query: VectorQuery, acl: AclFilter) -> list[VectorHit]: ...
    async def delete_document(self, document_id: str) -> None: ...
```

Qdrant implementation:

- collection alias `chunks_active`
- payload ACL filter
- collection snapshot/restore runbook

pgvector implementation:

- `chunk_embeddings` table
- HNSW index
- JSONB ACL payload filter

완료 조건:

- 같은 test corpus에서 Qdrant와 pgvector adapter contract test가 같은 권한 결과를 반환한다.
- ACL filter는 post-filter가 아니라 vector query 조건에 포함된다.
- Sprint 1 fake adapter contract proves deterministic upsert, ACL-required search, document delete exclusion, and no forbidden chunk leakage before real vector stores are connected.

### 4.6 Runtime Orchestrator

구현 API:

- `POST /api/v1/runs`
- `GET /api/v1/runs/{run_id}`
- `GET /api/v1/runs/{run_id}/steps`
- `GET /api/v1/runs/{run_id}/events`
- `POST /api/v1/runs/{run_id}/feedback`
- `POST /api/v1/retrieval-preview`

단계:

1. principal 생성
2. agent/version load
3. input guard
4. query rewrite/planner
5. ACL-aware vector search
6. rerank
7. answer generation
8. citation validator
9. output guard
10. run trace/audit 저장

완료 조건:

- 권한 없는 문서는 `retrieval_hits`, LLM context, citation에 나타나지 않는다.
- citation required agent가 citation 없이 답변하면 no-answer 또는 validation failure로 처리된다.
- run trace에서 단계별 latency와 실패 사유를 확인할 수 있다.

### 4.7 Eval API

구현 API:

- `GET/POST /api/v1/eval/cases`
- `POST /api/v1/eval/runs`
- `GET /api/v1/eval/runs/{eval_run_id}`
- `GET /api/v1/eval/runs/{eval_run_id}/results`
- `POST /api/v1/eval/runs/{eval_run_id}/approve-baseline`

완료 조건:

- synthetic corpus golden set을 batch 실행한다.
- ACL/citation/refusal scorer는 deterministic하게 pass/fail을 산출한다.
- report artifact를 MinIO에 저장하고 UI에서 링크한다.

## 5. Frontend 구현 계획

상세 화면 설계는 `notes/07_Frontend/Agent Studio 화면 설계.md`를 기준으로 한다.

### 5.1 Foundation

작업:

- Next.js App Router setup
- API client와 error handling
- auth/principal provider
- layout navigation
- table, badge, dialog, drawer, tabs, toast 공통 컴포넌트
- TanStack Query provider

완료 조건:

- `/agents`, `/knowledge`, `/eval`, `/audit`, `/admin/settings` shell route 접근 가능
- API problem response가 화면에서 request id와 함께 표시된다.

### 5.2 Agent Flow

구현:

- Agent 목록
- Agent 상세
- Builder stepper
- version draft autosave
- validate/publish action

완료 조건:

- 신규 agent 생성 후 draft version 저장 가능
- validation error가 field 단위로 표시된다.
- publish 후 목록과 상세에 published badge가 반영된다.

### 5.3 Knowledge Flow

구현:

- Knowledge source 목록/상세
- 문서 업로드
- ACL 편집
- index job polling
- chunk/citation preview

완료 조건:

- 업로드 후 job 상태가 queued/running/succeeded/failed로 갱신된다.
- ACL 변경 시 audit reason 입력을 요구한다.

### 5.4 Test Chat / Trace

구현:

- draft/published version 테스트
- SSE event stream
- citation chips와 source preview
- Run Trace Viewer
- retrieval hits table

완료 조건:

- Test Chat에서 답변과 citation을 확인할 수 있다.
- run id 클릭으로 Trace Viewer에 진입한다.
- 권한 없는 문서 내용은 preview되지 않는다.

### 5.5 Eval / Admin

구현:

- Eval suite 실행/결과 목록
- baseline diff
- Admin model/settings read view
- Audit Explorer

완료 조건:

- 평가 실행 후 suite별 pass rate와 실패 case가 표시된다.
- audit event를 기간/타입/대상으로 필터링할 수 있다.

## 6. DevOps/MLOps 구현 계획

상세 운영 설계는 `notes/08_DevOps_MLOps/폐쇄망 배포 구상.md`를 기준으로 한다.

### 6.1 Local Compose

작업:

- `docker-compose.closednet.yaml`
- API/Web/Worker/PostgreSQL/Qdrant/MinIO/vLLM mock 또는 lightweight model
- seed data
- smoke script

완료 조건:

- 인터넷 없이 local registry/image tar 기준으로 기동 가능
- smoke script가 agent 생성, 문서 인덱싱, run 실행을 검증한다.

### 6.2 Offline Release Bundle

작업:

- image export
- Python wheelhouse
- pnpm store/cache
- model manifest
- checksum/SBOM
- install/rollback runbook

완료 조건:

- bundle checksum 검증 성공
- 폐쇄망 staging에서 fresh install 성공
- release manifest로 image/model/schema version을 추적 가능

### 6.3 Observability

작업:

- OpenTelemetry instrumentation
- Prometheus metrics
- Grafana dashboards
- JSON log format
- run_id/trace_id correlation

완료 조건:

- API latency, model timeout, vector latency, indexing queue depth가 dashboard에 표시된다.
- run trace와 OTel trace를 서로 찾을 수 있다.

### 6.4 Backup / Restore / Reindex

작업:

- PostgreSQL backup script
- MinIO backup policy
- Qdrant snapshot 또는 pgvector backup
- index rebuild command
- restore rehearsal checklist

완료 조건:

- DB+MinIO 복구 후 index rebuild로 검색 가능 상태를 재현한다.
- embedding 모델 변경 시 신규 collection/table로 blue/green 전환 가능하다.

## 7. QA/Eval 구현 계획

상세 기준은 `docs/evaluation-plan.md`와 `notes/09_QA_Eval/MVP 평가 기준.md`를 기준으로 한다.

작업:

- synthetic corpus 생성
- 30개 이상 golden set 작성
- deterministic scorer 구현
- eval runner worker
- regression report
- Playwright E2E
- backend integration test

완료 조건:

- ACL suite 100% pass 없이는 release 불가
- citation/refusal 기준을 report로 확인 가능
- 모델/프롬프트/검색 설정 변경 시 baseline diff가 생성된다.

## 8. Milestone

### M0. Skeleton

- API/Web skeleton
- DB migration base
- Compose 기동
- health/ready

Exit:

- 개발자가 한 명령으로 전체 stack을 띄울 수 있다.

### M1. Agent + Knowledge

- Agent CRUD/version
- Knowledge source/document upload
- MinIO 저장
- index job skeleton

Exit:

- UI에서 agent와 문서를 만들 수 있다.

### M2. Index + Retrieval

- parser/chunk/embed
- Qdrant 또는 pgvector adapter
- ACL filter
- retrieval preview

Exit:

- 권한별 검색 결과가 다르게 나온다.

### M3. Runtime + Trace

- `/runs`
- answer generation
- citation validator
- run_step/retrieval_hit/audit 저장
- Test Chat/Trace Viewer

Exit:

- published agent에 질문하고 citation이 있는 답변을 받는다.

### M4. Eval + Hardening

- golden set/eval runner
- frontend E2E
- backend integration/security tests
- observability dashboards

Exit:

- release gate 기준을 자동 report로 판단한다.

### M5. Closed-net Release

- offline bundle
- install runbook
- backup/restore
- staging deployment

Exit:

- 인터넷 없는 staging에서 설치, smoke, quick eval을 완료한다.

## 9. 주요 의사결정 필요 항목

| 항목 | 선택지 | 권장 |
|---|---|---|
| Vector DB | Qdrant vs pgvector | corpus 성장/ACL filter 고려 시 Qdrant 우선, 단순 PoC는 pgvector |
| Queue | Redis/Celery vs PostgreSQL job table | MVP는 PostgreSQL job table, 운영 규모 커지면 Redis/Celery |
| Model Serving | vLLM vs Ollama vs 사내 gateway | 운영은 vLLM 또는 사내 gateway, 개발은 Ollama 허용 |
| Auth | SSO 연동 vs mock header | 운영 SSO, dev mock header |
| Confidential docs | MVP 포함 vs 제외 | 기본 제외, 별도 승인 후 확장 |

## 10. Definition of Done

- 코드: lint/typecheck/unit/integration 통과
- API: OpenAPI schema와 contract test 갱신
- DB: migration과 seed 검증
- UI: 주요 flow Playwright 통과
- RAG: ACL/citation/refusal quick eval 통과
- 운영: metrics/log/trace 확인
- 보안: audit event와 권한 체크 확인
- 문서: runbook 또는 설계 노트 갱신

## 11. 즉시 다음 액션

1. Backend skeleton과 DB migration base 생성
2. API OpenAPI 초안과 Pydantic schema 작성
3. Agent/Version/Knowledge/Document 핵심 테이블 migration
4. Next.js App shell과 Agent 목록 route 작성
5. MinIO upload와 index job skeleton 구현
6. Synthetic corpus와 golden set v0.1 작성
7. Compose 기반 local stack 구성
