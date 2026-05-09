# ACL 기반 검색 설계

## 원칙

권한 필터는 검색 이후가 아니라 검색 조건 단계에서 먼저 적용한다. 사용자가 볼 수 없는 문서는 LLM 컨텍스트, rerank 입력, 로그 원문, citation 후보 어디에도 들어가면 안 된다.

MVP 원칙은 다음과 같다.

- deny가 allow보다 우선한다.
- 클라이언트가 전달한 권한은 신뢰하지 않고 서버에서 사내 IAM/SSO를 재조회한다.
- ACL을 해석할 수 없는 문서는 검색 대상에서 제외한다.
- 권한 검사는 vector search 이전 payload filter와 최종 응답 전 Security Guard에서 이중 수행한다.
- audit log에는 어떤 ACL 조건이 적용되었는지 남기되, 불필요한 원문은 저장하지 않는다.

## 권한 축

| 축 | 예시 | 설명 |
|---|---|---|
| `user_id` | `u12345` | 개인 allow/deny 예외 |
| `department_id` | `security`, `hr` | 소속 부서 |
| `role` | `employee`, `manager`, `policy_owner` | 업무 역할 |
| `clearance_level` | `public`, `internal`, `confidential`, `restricted` | 기밀 등급 |
| `project_scope` | `corp-policy`, `project-a` | 프로젝트/업무 범위 |
| `employment_type` | `employee`, `contractor`, `external_guest` | 사용자 유형 |
| `time_window` | `effective_from`, `effective_to` | 문서 유효 기간 |

## ACL metadata 모델

chunk payload에는 검색 엔진에서 필터링 가능한 형태의 ACL metadata가 있어야 한다.

```yaml
acl:
  allow_user_ids: []
  deny_user_ids: ["u99999"]
  department_scope: ["all", "security"]
  role_scope: ["employee", "security_manager"]
  project_scope: ["corp-policy"]
  confidentiality_level: "internal"
  employment_scope: ["employee", "contractor"]
  effective_from: "2026-05-01"
  effective_to: null
  legal_hold: false
```

기밀 등급은 순서를 가진 enum으로 관리한다.

```text
public < internal < confidential < restricted
```

사용자의 `clearance_level`보다 높은 chunk는 검색에서 제외한다.

## 사용자 권한 컨텍스트

Runtime은 매 요청마다 권한 컨텍스트를 생성한다.

```yaml
auth_context:
  user_id: "u12345"
  user_id_hash: "sha256-..."
  department_id: "security"
  roles: ["employee", "policy_reader"]
  clearance_level: "internal"
  project_scopes: ["corp-policy"]
  employment_type: "employee"
  resolved_at: "2026-05-09T09:30:00+09:00"
  source: "internal_iam"
```

캐시를 쓰더라도 TTL은 짧게 둔다. 권한 회수나 부서 이동이 늦게 반영되면 보안 사고가 되므로, MVP는 5분 이하 TTL을 권장한다.

## ACL filter 생성

예시 논리식:

```text
NOT acl.deny_user_ids contains user_id
AND (
  acl.allow_user_ids contains user_id
  OR acl.department_scope contains "all"
  OR acl.department_scope contains auth_context.department_id
)
AND acl.role_scope intersects auth_context.roles
AND acl.project_scope intersects auth_context.project_scopes
AND acl.employment_scope contains auth_context.employment_type
AND acl.confidentiality_level <= auth_context.clearance_level
AND acl.effective_from <= now
AND (acl.effective_to is null OR acl.effective_to >= now)
AND acl.legal_hold = false
```

검색 엔진별 payload filter 표현은 다를 수 있지만, 위 의미를 보존해야 한다. vector DB가 enum 비교를 지원하지 않으면 `confidentiality_rank` 숫자 필드를 추가한다.

```yaml
confidentiality_level: "internal"
confidentiality_rank: 1
```

## 검색 단계

1. 사용자 권한 컨텍스트를 IAM에서 생성한다.
2. Agent Card의 knowledge source와 사용자 권한을 교차 검증한다.
3. query embedding을 생성한다.
4. vector search와 lexical search 모두에 ACL payload filter를 적용한다.
5. 후보 chunk를 hybrid merge한다.
6. rerank 입력에도 허용된 chunk만 전달한다.
7. citation locator가 있는 chunk만 답변 컨텍스트로 전달한다.
8. Critic이 답변-citation 일치성을 검토한다.
9. Security Guard가 최종 답변의 권한 위반을 재검사한다.

## Rerank와 ACL의 관계

rerank는 권한 필터 이후에만 수행한다. 권한 밖 chunk를 reranker에 넣으면 reranker 로그나 모델 컨텍스트에 원문이 남을 수 있기 때문이다.

```text
잘못된 순서: search -> rerank -> ACL filter
올바른 순서: ACL filter -> search -> merge -> rerank
```

MVP에서 rerank 로그에는 chunk 원문 전체를 저장하지 않고 다음 값만 저장한다.

- `run_id`
- `chunk_id`
- `document_id`
- `rerank_score`
- `score_version`
- `acl_decision=allow`

## Citation 노출 정책

사용자에게 보여줄 citation은 업무적으로 확인 가능한 locator를 제공하되 내부 경로나 보안 metadata를 노출하지 않는다.

권장 표시:

```text
[외부 반출 보안 절차, 3.2 로그 및 진단자료, p.12, v2026.05.01]
```

노출 금지:

- 내부 파일 서버 절대 경로
- object storage URI
- 문서 작성자 개인 ID
- 권한 필터 상세식
- 사용자가 권한 없는 문서의 제목/존재 여부

권한 없는 문서 때문에 답변할 수 없는 경우에도 "권한 없는 문서가 있습니다"라고 말하지 않는다. 대신 "현재 권한으로 확인 가능한 근거가 부족합니다"라고 답한다.

## 실패 처리

| 상황 | 처리 |
|---|---|
| IAM 조회 실패 | 검색 중단, 안전 실패 응답 |
| ACL filter 생성 실패 | 검색 중단, 보안 이벤트 기록 |
| ACL metadata 누락 chunk 발견 | 해당 chunk 제외, 인덱스 품질 이벤트 기록 |
| 검색 결과 0건 | 추측 금지, 확인 가능한 근거 부족 응답 |
| rerank 중 오류 | 정책에 따라 lexical/vector score 기반 fallback 또는 안전 실패 |
| 최종 답변 권한 위반 | 마스킹 또는 차단 |

## 감사 로그

감사 로그는 사후 조사에 필요한 결정을 남기되 민감 원문을 최소화한다.

```yaml
run_id: "run_20260509_000001"
agent_id: "security_policy_assistant"
build_id: "security_policy_assistant:1.3.0:sha256-..."
user_id_hash: "sha256-..."
auth_context_hash: "sha256-..."
source_ids: ["security_policy_docs"]
index_snapshot_id: "idx_security_policy_2026_05_01"
acl_filter_hash: "sha256-..."
retrieved_chunk_ids:
  - "sec-policy-2026:2026.05.01:p12:c03:8f2a91"
blocked_chunk_count: 0
security_flags: []
decision: "answered"
created_at: "2026-05-09T09:30:05+09:00"
```

`acl_filter_hash`는 실제 필터식을 그대로 노출하지 않으면서 재현성 확인에 쓴다. 필요 시 보안 감사자만 복호화 가능한 별도 secure audit store에 원문 필터를 저장한다.

## MVP Quality Gates

- 모든 검색 요청은 `auth_context.source=internal_iam`이어야 한다.
- 모든 retrieval trace는 `acl_filter_applied=true`를 포함해야 한다.
- vector/lexical/rerank 각 단계에 권한 밖 chunk 원문이 들어가지 않아야 한다.
- 검색 결과 chunk의 `confidentiality_rank`는 사용자 clearance rank 이하이어야 한다.
- citation에는 사용자에게 노출 가능한 locator만 포함해야 한다.
- 권한 회수 테스트에서 5분 이내 검색 차단이 확인되어야 한다.
