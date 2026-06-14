# Document ACL Editing + Revocation Propagation — Design

- **Date:** 2026-06-14
- **Slice:** 1/4 (보안 품질게이트 — 권한 회수 → 검색 제외 검증 + ACL 편집)
- **Branch:** `feat/document-acl-edit-revocation`

## Background

`rag-design`의 품질게이트 *"권한 회수 후 5분 이내 retrieval 차단"* 이 미검증 상태였다(점검에서 식별).
현재 문서 ACL은 업로드/등록 시 `access_groups` + `confidentiality_level` 지정만 가능하고,
이후 **편집·회수 경로가 없으며 회수가 검색에 반영되는지 검증된 적이 없다.**

### 핵심 아키텍처 사실 (탐색 결과)

- 문서 ACL은 Postgres `documents.access_groups`(JSON list) + `documents.confidentiality_level`(str)에 저장.
- 검색 시 ACL은 **in-query Qdrant payload 필터**로 강제된다:
  - `build_qdrant_acl_filter` → `access_groups`(MatchAny) + `confidentiality_rank`(Range) + `status==indexed`.
  - `payload_allows` → 동일 의미의 defense-in-depth 재검사.
  - **둘 다 chunk payload를 읽고, Postgres는 보지 않는다.**
- 따라서 **회수는 Qdrant chunk payload를 갱신해야 즉시 반영된다.** Postgres만 바꾸면
  in-query 필터가 stale payload를 그대로 통과시켜 누출된다.
- 재임베딩은 불필요하다 — ACL은 payload 전용 필드(`access_groups`, `confidentiality_rank`)이므로
  `set_payload`(by `document_id` 필터)면 충분하다.
- `FakeVectorStore`는 live Postgres `Document`를 읽으므로, 인메모리 계약테스트는
  Postgres 변경만으로 회수가 반영된다. 실제 payload 동기화 경로는 Qdrant 단위테스트 + 라이브로 검증한다.
- audit 인프라(`write_audit_event`)는 이미 `reason` 파라미터를 지원한다.

## Goal / Scope (YAGNI)

문서 ACL(`access_groups`, `confidentiality_level`)을 업로드 후 변경할 수 있고,
변경이 검색에 **즉시** 반영되며, 모든 변경이 `reason`과 함께 감사된다.

**범위 결정(사용자 확정):**
- **백엔드 전용.** UI 편집 폼은 이번 슬라이스 제외 → 백로그(버전 라이프사이클 UI 슬라이스)로 이월.
- **전체 교체(set semantics).** `access_groups`는 새 리스트로 통째 교체. 회수 = 그룹을 뺀 새 리스트 전송.
  델타 add/remove는 도입하지 않는다.

## 비범위 (YAGNI)

- ACL 편집 UI 폼, 델타 add/remove, knowledge-source 단위 ACL 캐스케이드,
  스케줄된 ACL 재평가, SSO 연동(헤더 스텁 유지).

## Components

### 1. Schema — `DocumentAclUpdate` (Pydantic)
- `access_groups: list[str]` — 전체 교체. `min_length=1`(빈 리스트는 deny-by-default로 문서를 고립시키므로 거부).
- `confidentiality_level: str` — `CONFIDENTIALITY_RANK` 키 중 하나로 검증(아니면 422).
- `reason: str = Field(min_length=1)` — 필수. 감사 기록용.

### 2. Vector store protocol — `set_document_acl`
시그니처: `set_document_acl(document_id, *, access_groups, confidentiality_rank) -> int` (갱신된 point 수 반환).
- `QdrantVectorStore`: `client.set_payload(payload={"access_groups": [...], "confidentiality_rank": n}, points_selector=FilterSelector(document_id == id))`,
  이어서 `count`로 영향 point 수 산정. 컬렉션 없으면 0.
- `FakeVectorStore`: 호출을 기록(`_acl_updates`)하고 영향 chunk 수를 반환 — fake는 live Postgres를 읽으므로 검색은 이미 반영됨.

### 3. Endpoint — `PATCH /api/v1/knowledge/documents/{document_id}/acl`
1. 문서 로드(없으면 404). before-state 캡처(`access_groups`, `confidentiality_level`).
2. `Document.access_groups` + `confidentiality_level` 갱신.
3. 각 `DocumentChunk.acl_snapshot` 갱신(Postgres 일관성).
4. `get_vector_store().set_document_acl(...)` 호출로 Qdrant payload 동기화.
5. `write_audit_event("document.acl_changed", reason=reason, payload={before, after, chunks_synced})`.
6. 갱신된 `DocumentRead` 반환.

### 4. Error handling — fail-closed
- Qdrant payload 동기화가 예외를 던지면 PATCH 전체 실패(트랜잭션 롤백) — Postgres와 Qdrant ACL을 절대 불일치 상태로 두지 않는다.
- 잘못된 confidentiality / 빈 access_groups / reason 누락 → 422.

## Data flow (회수 시나리오)

```
PATCH .../{doc}/acl {access_groups:[department:HR], confidentiality_level:internal, reason:"..."}
  → Document.access_groups = [department:HR]            (Postgres)
  → DocumentChunk.acl_snapshot 갱신                      (Postgres)
  → QdrantVectorStore.set_document_acl(doc, [department:HR], rank=1)  (Qdrant payload)
  → audit_event(document.acl_changed, reason, before/after)
다음 검색(같은 Finance 사용자): in-query 필터에서 access_groups 교집합 없음 → 제외(no_leak)
```

## Testing

- **계약테스트(인메모리, Fake):**
  - register+index 문서(group `all-employees`) → Finance 사용자가 preview에서 노출 확인.
  - PATCH로 `["department:HR"]` 회수 → 같은 사용자가 더 이상 노출 안 됨(`denied_count` 증가), 감사 이벤트(reason + before/after) 기록.
  - 빈 `access_groups` → 422. 잘못된 confidentiality → 422. `reason` 누락 → 422. 미존재 문서 → 404.
- **단위테스트(Qdrant `:memory:`):** `set_document_acl`이 payload를 실제로 갱신하고, 회수 후 같은 principal 검색에서 hit가 사라짐.
- **라이브(실 Qdrant):** 회수 전/후 retrieval-hit 수 차이 + audit row 존재 확인. docs에 결과 1절.
- **정직 단서:** 검색 신호는 결정적이라 신뢰 가능.

## Completion criteria

- ACL 변경 시 Qdrant payload로 즉시 반영, 회수 문서가 검색/인용에서 제외(계약+단위테스트로 입증).
- `audit_event`에 acl 변경 기록(reason).
- pytest 풀스위트 그린(.env 옆으로; baseline 81). ruff 클린. security-review(ACL 경로).
- 라이브: 회수 전/후 retrieval-hits 차이 + 감사 기록 확인.
