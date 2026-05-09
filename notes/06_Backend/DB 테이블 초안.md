# DB 테이블 초안

## 1. 저장소 역할

- PostgreSQL: 시스템의 source of truth. agent 설정, 문서 메타데이터, ACL, 실행 로그, 평가 결과, 감사 이벤트를 저장한다.
- Qdrant 또는 pgvector: chunk embedding과 vector 검색 index. MVP 의사결정 전까지 adapter 인터페이스를 동일하게 유지한다.
- MinIO: 원본 문서, 파싱 결과, chunk snapshot, eval report artifact를 저장한다.
- Redis 또는 PostgreSQL advisory lock: 인덱싱/평가 job 중복 실행 방지. Redis는 선택 사항이다.

## 2. 공통 컬럼 규칙

모든 업무 테이블은 아래 컬럼을 기본으로 둔다.

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | `uuid` 또는 prefix ULID text | 외부 노출 가능한 식별자. MVP는 `agt_`, `doc_` 등 prefix ULID를 권장 |
| `created_at` | `timestamptz` | 생성 시각 |
| `updated_at` | `timestamptz` | 수정 시각 |
| `created_by` | `text` | 생성 사용자 |
| `updated_by` | `text` | 마지막 수정 사용자 |
| `deleted_at` | `timestamptz null` | soft delete |

상태값은 PostgreSQL enum보다 text + check constraint를 우선한다. 폐쇄망 고객별 상태 확장이 필요할 수 있기 때문이다.

## 3. 핵심 테이블 개요

| 테이블 | 목적 | MVP 우선순위 |
|---|---|---|
| `users_cache` | IdP 사용자/부서/역할 캐시 | P1 |
| `agents` | 에이전트 기본 정보 | P0 |
| `agent_versions` | 프롬프트, 모델, 도구, 정책 버전 | P0 |
| `agent_version_tools` | 버전별 도구 연결 | P1 |
| `tools` | 등록된 사내 도구/API | P1 |
| `tool_permissions` | 도구별 사용 권한 | P1 |
| `knowledge_sources` | 문서 저장소, 파일 업로드 묶음, 파일서버 소스 | P0 |
| `documents` | 문서 메타데이터와 원본 객체 위치 | P0 |
| `document_chunks` | RAG chunk 메타데이터 | P0 |
| `document_acl` | 문서별 사용자/부서/역할 권한 | P0 |
| `index_jobs` | 문서 파싱/embedding/indexing 작업 | P0 |
| `runs` | 에이전트 실행 단위 | P0 |
| `run_steps` | planner/retriever/generator/guard 단계 로그 | P0 |
| `retrieval_hits` | 실행별 검색 후보와 citation 후보 | P0 |
| `tool_calls` | 도구 호출 기록 | P1 |
| `approvals` | human-in-the-loop 승인 기록. MVP는 구조만 | P2 |
| `eval_cases` | 평가셋 case | P0 |
| `eval_runs` | 평가 실행 묶음 | P0 |
| `eval_results` | case별 평가 결과 | P0 |
| `audit_events` | 보안/운영 감사 이벤트 | P0 |
| `system_settings` | 모델, 검색, 보존기간 기본값 | P1 |

## 4. Agent Registry

### `agents`

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | `text pk` | `agt_...` |
| `name` | `text not null` | 화면 표시명 |
| `slug` | `text unique` | URL/검색용 |
| `description` | `text` | 목적 설명 |
| `owner_user_id` | `text not null` | 소유자 |
| `owner_department_id` | `text not null` | 소유 부서 |
| `status` | `text not null` | `draft`, `published`, `archived` |
| `published_version_id` | `text null fk` | 현재 배포 버전 |
| `tags` | `jsonb not null default '[]'` | 검색 태그 |
| `visibility` | `text not null default 'department'` | `private`, `department`, `organization` |
| `created_at` 등 | 공통 |  |

인덱스:

- `idx_agents_owner_department_status(owner_department_id, status)`
- `idx_agents_tags_gin(tags jsonb_path_ops)`

### `agent_versions`

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | `text pk` | `agv_...` |
| `agent_id` | `text fk agents(id)` | 소속 agent |
| `version_no` | `int not null` | agent 내 증가 번호 |
| `version_name` | `text` | 사람이 읽는 버전명 |
| `status` | `text not null` | `draft`, `validated`, `published`, `superseded`, `rejected` |
| `system_prompt` | `text not null` | 시스템 지시문 |
| `model_config` | `jsonb not null` | chat model, temperature, token limit |
| `retrieval_config` | `jsonb not null` | top_k, rerank, min_score, source ids |
| `policy_config` | `jsonb not null` | citation 필수, 등급, PII masking |
| `response_format` | `jsonb not null default '{}'` | citation 형식, tone |
| `validation_result` | `jsonb null` | publish 전 검증 결과 |
| `published_at` | `timestamptz null` | 배포 시각 |
| `published_by` | `text null` | 배포자 |

제약:

- `(agent_id, version_no)` unique
- published 상태는 agent별 하나만 허용. 부분 unique index 사용: `where status = 'published'`

### `agent_version_tools`

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `agent_version_id` | `text fk` |  |
| `tool_id` | `text fk` |  |
| `tool_config` | `jsonb not null default '{}'` | timeout, allowed operations |
| `enabled` | `boolean default true` |  |

## 5. Tool Registry

### `tools`

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | `text pk` | `tool_...` |
| `name` | `text not null` | 도구명 |
| `description` | `text` | 설명 |
| `tool_type` | `text not null` | `http`, `sql_readonly`, `retrieval`, `internal` |
| `schema` | `jsonb not null` | OpenAPI subset 또는 function schema |
| `endpoint_ref` | `text null` | 직접 URL 대신 secret/config ref |
| `risk_level` | `text not null` | `low`, `medium`, `high` |
| `write_capable` | `boolean default false` | MVP에서는 false만 연결 허용 |
| `status` | `text not null` | `active`, `disabled`, `deprecated` |

### `tool_permissions`

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `tool_id` | `text fk` |  |
| `principal_type` | `text` | `user`, `department`, `role` |
| `principal_id` | `text` | 대상 ID |
| `permission` | `text` | `use`, `admin` |
| `conditions` | `jsonb default '{}'` | 시간, IP, 환경 등 |

## 6. Knowledge / Document

### `knowledge_sources`

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | `text pk` | `ks_...` |
| `name` | `text not null` | 소스명 |
| `source_type` | `text not null` | `upload`, `filesystem`, `sharepoint`, `db` |
| `description` | `text` |  |
| `owner_department_id` | `text not null` | 소유 부서 |
| `default_confidentiality_level` | `text not null` | 기본 등급 |
| `default_acl` | `jsonb not null default '{}'` | 신규 문서 기본 ACL |
| `ingestion_config` | `jsonb not null default '{}'` | parser/chunk 기본값 |
| `status` | `text not null` | `active`, `paused`, `archived` |

### `documents`

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | `text pk` | `doc_...` |
| `knowledge_source_id` | `text fk` |  |
| `title` | `text not null` | 제목 |
| `source_uri` | `text null` | 외부 소스 원 위치 |
| `object_uri` | `text not null` | MinIO 원본 위치 |
| `mime_type` | `text not null` |  |
| `file_size_bytes` | `bigint` |  |
| `sha256` | `text not null` | 중복/무결성 |
| `confidentiality_level` | `text not null` | `public`, `internal`, `restricted`, `confidential` |
| `department_scope` | `jsonb not null default '[]'` | 검색 허용 부서 |
| `metadata` | `jsonb not null default '{}'` | page count, author, date |
| `status` | `text not null` | `uploaded`, `indexed`, `index_failed`, `revoked` |
| `indexed_at` | `timestamptz null` | 최근 성공 인덱싱 |

인덱스:

- `idx_documents_source_status(knowledge_source_id, status)`
- `idx_documents_sha256(sha256)`
- `idx_documents_department_scope_gin(department_scope jsonb_path_ops)`

### `document_acl`

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | `text pk` | `acl_...` |
| `document_id` | `text fk documents(id)` |  |
| `principal_type` | `text not null` | `user`, `department`, `role`, `project` |
| `principal_id` | `text not null` | 대상 |
| `permission` | `text not null` | `read`, `admin` |
| `effect` | `text not null default 'allow'` | `allow`, `deny` |
| `expires_at` | `timestamptz null` | 임시 권한 |

권한 판단 우선순위:

1. explicit deny
2. explicit user allow
3. department/role/project allow
4. confidentiality level과 user clearance 확인
5. 기본 deny

### `document_chunks`

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | `text pk` | `chk_...` |
| `document_id` | `text fk` |  |
| `chunk_index` | `int not null` | 문서 내 순번 |
| `content` | `text not null` | 검색/생성에 쓰는 텍스트 |
| `content_hash` | `text not null` | 재색인 비교 |
| `token_count` | `int` |  |
| `page_start` | `int null` | citation |
| `page_end` | `int null` | citation |
| `section_path` | `jsonb not null default '[]'` | 제목 계층 |
| `metadata` | `jsonb not null default '{}'` | 표/이미지/셀 정보 |
| `vector_ref` | `text not null` | Qdrant point id 또는 pgvector row id |
| `embedding_model` | `text not null` | embedding 모델 |
| `indexed_at` | `timestamptz not null` |  |

Qdrant payload 또는 pgvector metadata에는 최소 다음 값을 복제한다.

```json
{
  "chunk_id": "chk_...",
  "document_id": "doc_...",
  "knowledge_source_id": "ks_...",
  "department_scope": ["hr"],
  "confidentiality_level": "restricted",
  "acl_principals": ["department:hr", "role:hr_manager"],
  "status": "indexed"
}
```

### `index_jobs`

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | `text pk` | `ijob_...` |
| `document_id` | `text fk` | 대상 문서 |
| `status` | `text not null` | `queued`, `running`, `succeeded`, `failed`, `cancelled` |
| `stage` | `text` | `parse`, `chunk`, `embed`, `upsert` |
| `config` | `jsonb not null` | parser/chunk/embed 설정 |
| `error_code` | `text null` | 실패 코드 |
| `error_message` | `text null` | 운영자용 메시지 |
| `started_at` | `timestamptz null` |  |
| `finished_at` | `timestamptz null` |  |
| `artifact_uri` | `text null` | 파싱 결과 snapshot |

## 7. Runtime / Trace

### `runs`

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | `text pk` | `run_...` |
| `agent_id` | `text fk` | 실행 agent |
| `agent_version_id` | `text fk` | 실행 시점 버전 |
| `user_id` | `text not null` | 호출자 |
| `department_id` | `text not null` | 호출 당시 부서 |
| `input_message` | `text not null` | 사용자 질문 |
| `input_metadata` | `jsonb default '{}'` | 첨부, UI context |
| `status` | `text not null` | `queued`, `running`, `succeeded`, `failed`, `policy_denied` |
| `answer` | `text null` | 최종 답변 |
| `answer_metadata` | `jsonb default '{}'` | citation summary, guardrail |
| `latency_ms` | `int null` | 전체 응답 시간 |
| `token_usage` | `jsonb default '{}'` | prompt/completion/embedding |
| `error_code` | `text null` | 실패 코드 |
| `trace_id` | `text not null` | OpenTelemetry trace |

보존: MVP 기본 180일. 민감 고객은 answer 저장을 비활성화하고 artifact hash만 저장하는 옵션을 둔다.

### `run_steps`

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | `text pk` | `step_...` |
| `run_id` | `text fk` |  |
| `step_order` | `int not null` | 순서 |
| `step_type` | `text not null` | `guard_input`, `planner`, `retriever`, `reranker`, `generator`, `guard_output` |
| `status` | `text not null` | `started`, `succeeded`, `failed`, `skipped` |
| `input_summary` | `jsonb default '{}'` | 원문 전체 대신 요약/해시 우선 |
| `output_summary` | `jsonb default '{}'` | 검색 count, 점수, guard result |
| `started_at` | `timestamptz` |  |
| `finished_at` | `timestamptz` |  |
| `latency_ms` | `int` |  |
| `error_code` | `text null` |  |

### `retrieval_hits`

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | `text pk` | `rhit_...` |
| `run_id` | `text fk` |  |
| `chunk_id` | `text fk document_chunks(id)` | 후보 chunk |
| `document_id` | `text fk documents(id)` | 역정규화 |
| `rank_original` | `int` | vector search 순위 |
| `rank_reranked` | `int null` | reranker 후 순위 |
| `score_vector` | `numeric` |  |
| `score_rerank` | `numeric null` |  |
| `used_in_context` | `boolean default false` | LLM context 포함 여부 |
| `used_as_citation` | `boolean default false` | 답변 citation 여부 |
| `acl_filter_snapshot` | `jsonb not null` | 당시 권한 필터 |

## 8. Audit / Approval

### `audit_events`

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | `text pk` | `aud_...` |
| `event_type` | `text not null` | `run.created`, `acl.changed` 등 |
| `actor_user_id` | `text null` | 수행자 |
| `target_type` | `text not null` | `agent`, `document`, `run`, `system` |
| `target_id` | `text null` | 대상 |
| `severity` | `text not null` | `info`, `warning`, `critical` |
| `event_payload` | `jsonb not null` | 상세 |
| `request_id` | `text null` | API 요청 |
| `trace_id` | `text null` | OTel trace |
| `created_at` | `timestamptz` |  |

### `approvals`

MVP에서는 publish 승인과 write tool 승인 구조만 마련한다.

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | `text pk` | `apv_...` |
| `approval_type` | `text not null` | `agent_publish`, `tool_call` |
| `target_type` | `text not null` |  |
| `target_id` | `text not null` |  |
| `requested_by` | `text not null` |  |
| `approved_by` | `text null` |  |
| `status` | `text not null` | `requested`, `approved`, `rejected`, `expired` |
| `reason` | `text null` |  |

## 9. Eval

### `eval_cases`

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | `text pk` | `ecase_...` |
| `suite` | `text not null` | `rag-core`, `acl`, `citation`, `safety` |
| `question` | `text not null` | 입력 질문 |
| `expected_answer` | `text null` | 정답 요약 |
| `expected_citations` | `jsonb default '[]'` | document/page/chunk 기준 |
| `principal_context` | `jsonb not null` | 사용자/부서/역할 |
| `tags` | `jsonb default '[]'` | 난이도, 문서형 |
| `must_refuse` | `boolean default false` | 접근 불가/근거 부족 기대 |
| `status` | `text default 'active'` |  |

### `eval_runs`

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | `text pk` | `erun_...` |
| `agent_version_id` | `text fk` | 평가 대상 |
| `suite` | `text not null` | 실행 suite |
| `status` | `text not null` | `queued`, `running`, `succeeded`, `failed` |
| `config` | `jsonb not null` | 모델, seed, scoring 설정 |
| `summary` | `jsonb default '{}'` | pass rate, citation rate |
| `started_at` | `timestamptz null` |  |
| `finished_at` | `timestamptz null` |  |

### `eval_results`

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `id` | `text pk` | `eres_...` |
| `eval_run_id` | `text fk` |  |
| `eval_case_id` | `text fk` |  |
| `run_id` | `text fk runs(id)` | 실제 실행 로그 |
| `scores` | `jsonb not null` | faithfulness, citation, acl 등 |
| `passed` | `boolean not null` | 통과 여부 |
| `failure_reasons` | `jsonb default '[]'` | 실패 사유 |
| `review_status` | `text default 'pending'` | 수동 리뷰 |

## 10. Vector DB 선택별 스키마

### Qdrant 권장안

- collection: `agentforge_chunks_{embedding_model_version}`
- point id: `document_chunks.vector_ref`
- vector size: embedding model별 고정
- payload: ACL 필터에 필요한 값 전체 복제
- snapshot: 폐쇄망 백업을 위해 Qdrant snapshot 주기 저장

장점: payload filter, 운영 도구, 대량 vector 처리에 유리하다.

### pgvector 대안

`chunk_embeddings`

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `chunk_id` | `text pk fk document_chunks(id)` |  |
| `embedding_model` | `text not null` |  |
| `embedding` | `vector(n)` | pgvector |
| `payload` | `jsonb not null` | ACL 필터 복제 |

인덱스:

- HNSW: `using hnsw (embedding vector_cosine_ops)`
- payload GIN: `payload jsonb_path_ops`

장점: 운영 단순성. 단점: 대규모 corpus와 filter 조합에서 성능 검증 필요.

## 11. Migration 우선순위

1. `agents`, `agent_versions`, `knowledge_sources`, `documents`, `document_acl`
2. `document_chunks`, `index_jobs`, vector adapter 저장소
3. `runs`, `run_steps`, `retrieval_hits`, `audit_events`
4. `eval_cases`, `eval_runs`, `eval_results`
5. `tools`, `tool_permissions`, `approvals`, `system_settings`

## 12. 데이터 보존/삭제 정책

- 원본 문서: 문서 revocation 이후에도 감사 요구에 따라 90일 quarantine 후 삭제 가능.
- chunk/vector: 문서 revocation 즉시 검색 제외, batch worker가 vector delete 수행.
- run 입력/답변: 기본 180일. 보안 등급 높은 agent는 30일 또는 저장 안 함 옵션.
- audit event: 기본 1년 이상. 고객 보안 정책에 맞춰 WORM 스토리지 연계 가능.
