# API 초안

## 1. API 설계 원칙

- Base path: `/api/v1`
- 인증: 폐쇄망 SSO 또는 사내 IdP 연동을 전제로 하되, MVP 개발 환경은 `X-User-Id`, `X-Department-Id`, `X-Roles` 헤더 기반 mock principal을 허용한다.
- 권한: 모든 write API는 `admin` 또는 `agent_owner` 권한을 요구한다. 실행 API는 published agent에 대해 사용자 ACL 컨텍스트를 반드시 생성한다.
- 응답 포맷: JSON 기본, 파일 업로드는 `multipart/form-data`, 대용량 로그/실행 이벤트는 SSE 또는 cursor pagination.
- 에러 포맷: FastAPI 예외 핸들러에서 RFC 7807 계열 `application/problem+json` 형태로 통일한다.
- 멱등성: 문서 업로드, 인덱싱 job 생성, agent publish는 `Idempotency-Key` 헤더를 지원한다.
- 추적성: 모든 요청은 `X-Request-Id`를 수용하고 없으면 서버에서 생성한다. `run_id`, `trace_id`, `audit_event_id`와 연결한다.

## 2. 공통 모델

### Pagination

```json
{
  "items": [],
  "page": 1,
  "page_size": 50,
  "total": 124,
  "next_cursor": "optional-for-log-streams"
}
```

### Problem Response

```json
{
  "type": "https://agentforge.local/problems/policy-denied",
  "title": "Policy denied",
  "status": 403,
  "detail": "User cannot access the requested knowledge source.",
  "request_id": "req_01HX...",
  "code": "POLICY_DENIED"
}
```

### Principal Context

런타임과 검색 API 내부에서 다음 형태의 principal을 만든다.

```json
{
  "user_id": "u12345",
  "department_id": "finance",
  "roles": ["employee", "agent_user"],
  "clearance_level": "internal",
  "project_scopes": ["erp-modernization"]
}
```

## 3. Agent Registry API

| Method | Path | 설명 | 주요 권한 |
|---|---|---|---|
| `GET` | `/agents` | 에이전트 목록 조회. 상태, 소유자, 태그, 지식 소스 필터 지원 | `agent_user` |
| `POST` | `/agents` | 에이전트 shell 생성. 이름/목적/소유 부서만 저장 | `agent_owner` |
| `GET` | `/agents/{agent_id}` | 에이전트 상세와 latest/published version 요약 | `agent_user` |
| `PATCH` | `/agents/{agent_id}` | 이름, 설명, 태그, 소유 부서 수정 | `agent_owner` |
| `DELETE` | `/agents/{agent_id}` | soft delete. published version이 있으면 archive 상태로 전환 | `admin` |
| `GET` | `/agents/{agent_id}/versions` | 버전 목록 | `agent_owner` |
| `POST` | `/agents/{agent_id}/versions` | draft 버전 생성 | `agent_owner` |
| `GET` | `/agents/{agent_id}/versions/{version_id}` | 특정 버전 상세 | `agent_owner` |
| `PATCH` | `/agents/{agent_id}/versions/{version_id}` | draft 버전 수정 | `agent_owner` |
| `POST` | `/agents/{agent_id}/versions/{version_id}/validate` | publish 전 정책/스키마 검증 | `agent_owner` |
| `POST` | `/agents/{agent_id}/versions/{version_id}/publish` | 버전 배포. 기존 published는 superseded 처리 | `admin` 또는 승인된 `agent_owner` |
| `POST` | `/agents/{agent_id}/archive` | 에이전트 사용 중지 | `admin` |

### `POST /agents`

Request:

```json
{
  "name": "인사 규정 도우미",
  "description": "사내 인사 규정 문서를 근거로 답변하는 RAG 에이전트",
  "owner_department_id": "hr",
  "tags": ["hr", "policy"]
}
```

Response `201`:

```json
{
  "agent_id": "agt_01HX...",
  "name": "인사 규정 도우미",
  "status": "draft",
  "created_at": "2026-05-09T09:00:00+09:00"
}
```

### `POST /agents/{agent_id}/versions`

Request:

```json
{
  "version_name": "v0.1-draft",
  "system_prompt": "사용자가 접근 가능한 문서 근거만 사용해 한국어로 답변한다.",
  "model_config": {
    "chat_model": "local-llm-8b",
    "temperature": 0.2,
    "max_tokens": 1024
  },
  "retrieval_config": {
    "knowledge_source_ids": ["ks_hr_policy"],
    "top_k": 20,
    "rerank_top_k": 5,
    "min_score": 0.35,
    "citation_required": true
  },
  "tool_ids": [],
  "policy_config": {
    "allowed_confidentiality_levels": ["public", "internal", "restricted"],
    "deny_without_citation": true,
    "pii_masking": true
  }
}
```

검증 규칙:

- `knowledge_source_ids`는 사용자의 소유 부서 또는 admin 범위에 있어야 한다.
- `citation_required=true`인 agent는 답변 생성 시 citation이 없으면 `needs_more_context` 또는 `no_answer`를 반환한다.
- MVP에서는 write tool 연결을 거부하고 read-only tool만 허용한다.

## 4. Tool Registry API

MVP에서는 내부 API 호출 자동화보다 read-only tool 등록/표시를 우선한다.

| Method | Path | 설명 | 권한 |
|---|---|---|---|
| `GET` | `/tools` | 사용 가능한 도구 목록 | `agent_owner` |
| `POST` | `/tools` | 도구 등록. MVP에서는 admin 전용 | `admin` |
| `GET` | `/tools/{tool_id}` | 도구 스키마/권한 상세 | `agent_owner` |
| `PATCH` | `/tools/{tool_id}` | 도구 설명, OpenAPI schema, allowlist 수정 | `admin` |
| `GET` | `/tools/{tool_id}/permissions` | 도구 사용 가능 부서/역할 조회 | `admin` |
| `PUT` | `/tools/{tool_id}/permissions` | 도구 권한 교체 | `admin` |

도구 호출 결과는 항상 `tool_calls`와 `audit_events`에 남긴다. MVP에서 write tool은 `disabled_by_policy` 상태로만 모델링한다.

## 5. Knowledge Source / Document API

| Method | Path | 설명 | 권한 |
|---|---|---|---|
| `GET` | `/knowledge-sources` | 지식 소스 목록. 부서/상태/타입 필터 | `agent_owner` |
| `POST` | `/knowledge-sources` | 지식 소스 생성 | `agent_owner` |
| `GET` | `/knowledge-sources/{source_id}` | 지식 소스 상세와 인덱싱 요약 | `agent_owner` |
| `PATCH` | `/knowledge-sources/{source_id}` | 이름, 설명, 기본 ACL, chunk 정책 수정 | `agent_owner` |
| `POST` | `/knowledge-sources/{source_id}/sync` | 외부 소스 동기화 job 생성 | `agent_owner` |
| `GET` | `/documents` | 문서 목록. source/status/ACL 필터 | `agent_owner` |
| `POST` | `/documents` | 파일 업로드 및 document row 생성 | `agent_owner` |
| `GET` | `/documents/{document_id}` | 문서 메타데이터와 인덱싱 상태 | `agent_owner` |
| `PATCH` | `/documents/{document_id}` | 제목, 등급, ACL 수정 | `agent_owner` |
| `POST` | `/documents/{document_id}/index-jobs` | 파싱/chunk/embedding job 생성 | `agent_owner` |
| `GET` | `/index-jobs/{job_id}` | 인덱싱 job 상태 | `agent_owner` |
| `GET` | `/documents/{document_id}/chunks` | chunk 메타데이터와 citation preview | `agent_owner` |
| `POST` | `/documents/{document_id}/revoke` | 검색 제외 처리. 원본은 보존 | `admin` |

### `POST /documents`

`multipart/form-data`:

- `file`: PDF/DOCX/XLSX/TXT/MD
- `knowledge_source_id`
- `title`
- `confidentiality_level`: `public | internal | restricted | confidential`
- `department_scope`: 배열 문자열 또는 JSON
- `acl`: 사용자/부서/역할 ACL JSON

Response:

```json
{
  "document_id": "doc_01HX...",
  "object_uri": "s3://agentforge-documents/raw/doc_01HX/original.pdf",
  "status": "uploaded",
  "sha256": "..."
}
```

### `POST /documents/{document_id}/index-jobs`

Request:

```json
{
  "parser_profile": "default-ko",
  "chunking": {
    "strategy": "semantic-heading",
    "chunk_size": 900,
    "chunk_overlap": 150
  },
  "embedding_model": "local-bge-m3",
  "force_reindex": false
}
```

처리 단계:

1. 원본 파일 checksum과 MIME 검증
2. MinIO에서 원본 다운로드
3. 텍스트 파싱 및 정규화
4. chunk 생성 및 `document_chunks` 저장
5. embedding 생성
6. Qdrant 또는 pgvector upsert
7. `index_jobs` 상태 갱신 및 audit event 기록

## 6. Runtime API

| Method | Path | 설명 | 권한 |
|---|---|---|---|
| `POST` | `/runs` | 에이전트 실행 생성. 동기 응답 또는 async 선택 | `agent_user` |
| `GET` | `/runs/{run_id}` | 실행 요약, 최종 답변, citation | 본인 또는 운영자 |
| `GET` | `/runs/{run_id}/steps` | planner/retriever/generator/guard 단계 로그 | 본인 또는 운영자 |
| `GET` | `/runs/{run_id}/events` | SSE 실행 이벤트 스트림 | 본인 |
| `POST` | `/runs/{run_id}/feedback` | 사용자 피드백 저장 | 본인 |
| `POST` | `/retrieval-preview` | Builder 테스트용 검색 preview. 답변 생성 없음 | `agent_owner` |

### `POST /runs`

Request:

```json
{
  "agent_id": "agt_01HX...",
  "agent_version_id": "agv_01HX...",
  "input": {
    "message": "육아휴직 신청 절차를 알려줘",
    "attachments": []
  },
  "mode": "sync",
  "debug": false
}
```

Response:

```json
{
  "run_id": "run_01HX...",
  "status": "succeeded",
  "answer": "육아휴직 신청은 ...",
  "citations": [
    {
      "document_id": "doc_01HX...",
      "chunk_id": "chk_01HX...",
      "title": "인사 규정",
      "page": 12,
      "score": 0.82
    }
  ],
  "latency_ms": 4820,
  "guardrail": {
    "pii_masked": false,
    "policy_result": "allowed"
  }
}
```

런타임 단계:

1. principal/context 생성
2. agent published version 로드
3. 입력 보안 검사 및 prompt injection heuristic
4. query rewrite 또는 planner step
5. ACL filter가 포함된 vector search
6. rerank 및 citation 후보 확정
7. 답변 생성
8. citation 검증, hallucination heuristic, 금칙어/민감정보 guard
9. run/run_step/audit 저장

## 7. Audit / Operation API

| Method | Path | 설명 | 권한 |
|---|---|---|---|
| `GET` | `/audit-events` | 감사 이벤트 검색 | `auditor`, `admin` |
| `GET` | `/tool-calls` | 도구 호출 기록 검색 | `auditor`, `admin` |
| `GET` | `/runs` | 실행 로그 검색. 사용자/에이전트/상태/기간 필터 | `ops`, `admin` |
| `GET` | `/metrics/runtime-summary` | 응답시간, 실패율, citation 누락률 요약 | `ops`, `admin` |
| `GET` | `/healthz` | liveness | 공개 내부망 |
| `GET` | `/readyz` | DB/vector/model gateway 의존성 readiness | 공개 내부망 |

감사 이벤트 타입:

- `agent.created`, `agent.version.published`, `document.uploaded`, `document.indexed`
- `run.created`, `run.policy_denied`, `run.no_citation`, `tool.called`
- `acl.changed`, `model.changed`, `admin.setting_changed`

## 8. Eval API

| Method | Path | 설명 | 권한 |
|---|---|---|---|
| `GET` | `/eval/cases` | 평가 케이스 목록 | `qa`, `admin` |
| `POST` | `/eval/cases` | 평가 케이스 생성 | `qa` |
| `POST` | `/eval/runs` | 평가 실행 생성 | `qa` |
| `GET` | `/eval/runs/{eval_run_id}` | 평가 실행 상태/요약 | `qa` |
| `GET` | `/eval/runs/{eval_run_id}/results` | case별 결과 | `qa` |
| `POST` | `/eval/runs/{eval_run_id}/approve-baseline` | 회귀 baseline 승격 | `qa`, `admin` |

평가 실행은 운영 run과 분리된 `eval_runs`, `eval_results`에 저장하되, 내부적으로 동일한 Runtime Orchestrator를 호출한다.

## 9. FastAPI 모듈 레이아웃 초안

```text
apps/api/
  main.py
  core/
    config.py
    security.py
    logging.py
    errors.py
  api/v1/
    agents.py
    tools.py
    knowledge.py
    documents.py
    runs.py
    audit.py
    eval.py
  domain/
    agents/
    documents/
    retrieval/
    runtime/
    policy/
    eval/
  infra/
    db.py
    minio.py
    qdrant.py
    pgvector.py
    model_gateway.py
    task_queue.py
  workers/
    indexing_worker.py
    eval_worker.py
  tests/
    contract/
    integration/
    policy/
```

## 10. 우선 구현 순서

1. DB migration, SQLAlchemy 모델, 공통 principal/auth dependency
2. Agent/Version CRUD와 publish 상태 전이
3. Knowledge Source/Document 업로드, MinIO 저장, index job 상태 모델
4. Qdrant 또는 pgvector adapter 인터페이스와 ACL filter contract
5. Runtime `/runs` happy path와 run_step/audit 저장
6. Agent Studio가 사용할 retrieval preview와 run trace API
7. Eval API와 golden set 회귀 실행
8. 운영 API, metrics, readiness probe 강화
