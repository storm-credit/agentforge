# AgentForge — Run Trace Viewer (`/runs`) 설계

- 날짜: 2026-06-07
- 상태: 설계 승인 대기
- Epic: EP-04 Runtime run (Run Trace Viewer) / 거버넌스·디버깅
- 선행: 런타임 run + run_steps + retrieval_hits + 진짜 벡터검색 모두 main.

## 1. 목적과 범위

운영자가 실행(run) 내역을 보고 **단계별 트레이스**(guard_input→retriever→generator→citation_validator→guard_output: 유형·상태·latency·핵심 출력)와 **검색 hit**(점수·랭크·인용여부·**청크 본문**·ACL 스냅샷), **degraded/거부 사유**를 확인하는 읽기 전용 화면.

업계 LLM 트레이스 뷰어(LangSmith/Langfuse/Phoenix) 관행 검증 결과 반영: "검색이 무엇을 반환했고 어떻게 랭크됐고 LLM이 본 컨텍스트는 무엇인가"의 드릴다운 + 단계별 latency가 핵심.

### 포함
- 신규 `/runs` 페이지(마스터-디테일) + 사이드바 "Runs".
- **작은 백엔드 추가**: `retrieval-hits` 응답에 청크 **content** 노출(데이터는 이미 DB에 있음, 미노출 상태).
- 단계 타임라인 + hit 표(본문 포함) + run 단위 ACL 스냅샷 + degraded/거부 강조.

### 제외 (의도)
- faithfulness/context-relevance 같은 **LLM-as-judge 평가 지표** → eval 하네스(EP-06) 영역, 트레이스 뷰어 아님.
- 토큰/비용 → 백엔드가 추적 안 함(표시 불가).
- 검색·필터·페이지네이션·피드백·실시간 갱신.

## 2. 백엔드 변경 (작게, 테스트 포함)
- `app/domain/schemas.py` `RetrievalHitRead`에 `content: str | None = None` 추가.
- `app/api/v1/runs.py` `list_run_retrieval_hits` 핸들러: hits 조회 후 `chunk_id`들로 `DocumentChunk.content`를 한 번에 조회(dict)하여 각 `RetrievalHitRead`에 `content` 채워 반환(없으면 None). 기존 필드·정렬(rank_original) 유지.
- **계약 테스트**: `test_runtime_contracts.py`에 "retrieval-hits가 chunk content를 포함한다" 추가.
- 다른 엔드포인트/스키마 무변경.

## 3. 프론트 구조
- 신규 `apps/web/app/runs/page.tsx` (클라이언트, 마스터-디테일).
- 수정 `apps/web/app/layout.tsx` — 네비에 `{ href: "/runs", label: "Runs" }` 추가(Chat 다음).
- 수정 `apps/web/app/lib/api.ts` — 헬퍼/타입 추가:
```
RunSummary  = { id; input: {message?:string}; status; latency_ms; started_at; answer; citations: {title;citation_locator}[]; guardrail: Record<string,unknown> }
RunStep     = { step_order; step_type; status; input_summary; output_summary; latency_ms; error_code; error_message }
RetrievalHit= { rank_original; title; citation_locator; score_vector; used_in_context; used_as_citation; chunk_id; content?: string; acl_filter_snapshot: Record<string,unknown> }
listRuns()              -> GET /runs
getRunSteps(id)         -> GET /runs/{id}/steps
getRunHits(id)          -> GET /runs/{id}/retrieval-hits
```
(이 GET들은 principal 불필요 — 공개 GET. §7 참고.)

## 4. 화면 (한 페이지)
- **좌측 목록**: `listRuns()` 최신순. 항목: 질문(`input.message`)·상태 배지·`latency_ms`·시간. 클릭 → 선택.
- **우측 상세**(선택 run):
  - **요약**: 답변 텍스트 + 출처 목록 + 가드레일(citation 통과/개수). 거부면 그 사실 강조.
  - **단계 타임라인**: 단계별 `step_type`·상태 배지·`latency_ms` 막대, 핵심 출력(generator: `mode/language`; retriever: `hit_count/denied_count/vector_adapter/degraded`; citation_validator: `passed`). `error_code/message` 있으면 빨강. `input_summary/output_summary` 펼쳐보기(details).
  - **검색 hit 표**: `rank`·제목·`score_vector`·인용여부(`used_as_citation`)·`citation_locator`·**본문(content, 접기/펼치기)**.
  - **ACL 스냅샷**: 첫 hit의 `acl_filter_snapshot`(subjects·clearance·vector_adapter)을 1회 표시(권한 필터 적용 증거).

## 5. 에러/빈 상태
- run 없음 → "아직 실행 내역이 없습니다 (/chat이나 빌더 테스트에서 질문해 보세요)".
- fetch 오류 → 인라인 메시지. 상세 로드 실패 시 해당 영역만 에러.

## 6. 테스트
- **백엔드 계약**: retrieval-hits 응답에 `content` 포함(인덱싱된 청크 본문) — `apps/api` pytest(.venv). 기존 56 + 1.
- **Playwright 렌더**: `/runs` heading + 목록/빈상태(백엔드 불요).
- **라이브 수동**: 이번 세션 run들 표시 → 클릭 시 단계 타임라인(`mode=llm`,`vector_adapter=qdrant`) + hit 본문 노출. 거부 run은 거부 사유 표시.

## 7. 알려진 한계 (보안)
`/runs*` GET은 현재 **인증 없음**(기존 open GET과 동일). 청크 본문 노출은 제목/답변 노출과 같은 부류의 MVP 한계 — 실제 SSO 도입(백로그 의존성) 시 이 트레이스 엔드포인트들을 principal 스코프로 제한해야 한다. (operator 헤더 스텁과 동일 선상.)

## 8. 영향 파일 요약
- 백엔드: `app/domain/schemas.py`(RetrievalHitRead+content), `app/api/v1/runs.py`(hits 핸들러 content 조인), `tests/test_runtime_contracts.py`(계약).
- 프론트: 신규 `app/runs/page.tsx`·`tests/runs.spec.ts`, 수정 `app/layout.tsx`·`app/lib/api.ts`.
