# Agent Build Spec

## 목적

Agent Build는 Agent Forge Runtime이 실행할 수 있는 에이전트 계약이다. MVP에서는 문서 기반 RAG 에이전트를 대상으로 하며, 모델/프롬프트/지식/권한/품질 게이트/로그 정책을 하나의 버전 고정 패키지로 묶는다.

## 빌드 불변성

- `agent_id`는 논리 에이전트를 식별한다.
- `version`은 사람이 관리하는 릴리스 버전이다.
- `build_id`는 Agent Card, prompt refs, model refs, tool refs, index snapshot refs를 해시한 불변 ID다.
- 운영 중인 build는 수정하지 않는다. 변경은 새 build로 배포한다.
- `index_snapshot_id`가 바뀌면 같은 Agent Card라도 새 build로 취급한다.

## Agent Card 필수 필드

```yaml
schema_version: "agentforge.agent_card/v1"
agent_id: "security_policy_assistant"
name: "보안규정 상담 에이전트"
version: "1.3.0"
status: "approved"
owner:
  department_id: "security"
  service_owner: "security-platform-team"
purpose: "사내 보안 규정과 반출 절차를 근거 기반으로 안내한다."
audience:
  allowed_departments: ["all"]
  allowed_roles: ["employee", "security_manager"]
input_contract:
  locales: ["ko-KR"]
  max_input_chars: 4000
  allowed_intents: ["policy_qa", "procedure_help", "document_summary"]
output_contract:
  format: "markdown"
  citation_required: true
model_policy:
  planner:
    provider: "internal_gateway"
    model: "local-llm-small"
    temperature: 0.0
  generator:
    provider: "internal_gateway"
    model: "local-llm-rag"
    temperature: 0.2
  critic:
    provider: "internal_gateway"
    model: "local-llm-small"
    temperature: 0.0
prompt_policy:
  system_prompt_ref: "prompts/security_policy_assistant/system@1.3.0"
knowledge_sources:
  - source_id: "security_policy_docs"
    collection: "corp_security_policy"
    index_snapshot_id: "idx_security_policy_2026_05_01"
retrieval_policy:
  vector_top_k: 40
  lexical_top_k: 20
  rerank_top_k: 8
  max_context_chunks: 6
security_policy:
  prompt_injection_detection: "enabled"
  pii_detection: "enabled"
  external_export:
    allowed: false
runtime_flow:
  - "security_precheck"
  - "plan"
  - "retrieve"
  - "generate"
  - "critic_review"
  - "security_finalcheck"
  - "format_response"
  - "audit_log"
quality_gates:
  build_time:
    - "schema_valid"
    - "knowledge_source_exists"
    - "acl_fields_present"
    - "golden_set_pass"
  runtime:
    - "acl_filter_applied"
    - "citation_coverage_pass"
    - "security_finalcheck_pass"
    - "audit_log_written"
observability:
  retention_days: 180
```

## Runtime Flow

```text
Ingress
-> Security Guard(pre-check)
-> Planner
-> Retriever
-> Answer Generator
-> Critic
-> Security Guard(final-check)
-> Response Formatter
-> Audit Logger
```

### Security Guard pre-check

- 사용자 입력의 prompt injection, ACL 우회, 개인정보/기밀 반출 의도를 검사한다.
- 차단 요청은 Planner 이후로 넘기지 않는다.
- 허용 가능한 업무 요청이지만 위험도가 있으면 `risk_level`을 RuntimeState에 남긴다.

### Planner

- intent를 분류하고 허용된 knowledge source와 검색 쿼리를 선택한다.
- Agent Card 밖의 도구, 문서, intent를 계획에 넣을 수 없다.
- 산출물은 `plan_steps`, `retrieval_targets`, `risk_level`이다.

### Retriever

- IAM에서 확인한 권한 컨텍스트로 ACL payload filter를 만든다.
- vector search와 lexical search에 ACL 필터를 먼저 적용한다.
- rerank에는 허용된 chunk만 전달한다.
- citation locator가 없는 chunk는 LLM 컨텍스트에서 제외한다.

### Critic

- 답변의 핵심 주장에 citation이 붙었는지 확인한다.
- citation이 실제 chunk 내용과 일치하는지 검토한다.
- 기준 미달이면 1회 재작성 요청 후, 실패 시 안전 응답으로 전환한다.

### Security Guard final-check

- 최종 답변의 개인정보, 기밀 원문 과다 노출, 권한 밖 문서 노출을 검사한다.
- 마스킹 또는 차단 결정을 audit log에 남긴다.

## MVP Quality Gates

### Build-time

- Agent Card schema validation 통과
- prompt/model/tool/knowledge source ref resolve 성공
- index snapshot 존재 및 active 상태 확인
- sample chunk ACL 필드 coverage 100%
- golden set의 정상 답변, 근거 부족, 권한 차단, prompt injection 케이스 통과
- 보안 검토자와 소유 부서 승인 기록 존재

### Runtime

- `auth_context`는 서버에서 IAM 재조회
- `acl_filter_applied=true` 없는 retrieval 결과 차단
- 근거형 답변 citation coverage 100%
- Security Guard pre/final check 수행률 100%
- audit log 기록 실패 시 성공 응답 금지
- 권한 밖 문서 원문이 LLM context, rerank input, 응답, 일반 로그에 남지 않음

## 운영 권장값

| 항목 | MVP 기본값 |
|---|---|
| p95 latency | 8초 이하 |
| max context chunks | 6 |
| rerank top-k | 8 |
| input length | 4000자 이하 |
| audit retention | 180일 이상 |
| IAM cache TTL | 5분 이하 |
