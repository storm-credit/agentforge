# AgentForge — 관련도 게이팅 (Relevance Gating) 설계

- 날짜: 2026-06-08
- 상태: 승인됨 (설계+구현단계 통합 — 소규모)
- 동기: live-v0.1 평가에서 **과답변** 발견(관련도 임계 없음 → 무관/권한밖 주제도 가까운 문서로 답함). citation/useful 100%·누출 0이나 거부 규율 약함.

## 1. 목적
검색된 청크가 충분히 관련되지 않으면 컨텍스트에서 제외 → 기존 "컨텍스트 없음 → 거부" 경로로 거부. 답변 가능한 질문 품질은 유지하면서 무관 질문은 거부하게 한다.

## 2. 접근 (기존 구조 재사용)
- `VectorQuery.min_score`는 이미 존재하고 `FakeVectorStore`는 이미 적용 중. 빠진 3가지만 채운다.
- 설정: `config.py`에 `retrieval_min_score: float = 0.0` (env `AGENT_FORGE_RETRIEVAL_MIN_SCORE`). 기본 0.0 = 현행 동작(회귀 0), 보정 후 값으로 설정.
- 런타임: `runs.py _search_authorized_context`가 `VectorQuery(..., min_score=get_settings().retrieval_min_score)`로 주입.
- Qdrant: `QdrantVectorStore.search`가 payload_allows 통과 후 `score_vector < query.min_score`인 hit 제거. 남은 게 없으면 빈 결과 → 거부.

## 3. 임계값 보정 (평가 하네스 스윕)
구현 후 `run_live_eval.py`를 `AGENT_FORGE_RETRIEVAL_MIN_SCORE` ∈ {0.0, 0.2, 0.3, 0.4}로 실행 → 거부 규율(c07/c08/c09 behavior_ok)↑ 하면서 useful%·citation%가 유지되는 값을 기본값으로 채택. before/after를 eval-results 문서에 기록.

## 4. 구현 단계 (TDD)
1. `config.py`: `retrieval_min_score` 필드 추가.
2. `qdrant_store.py`: search에서 `query.min_score` 필터 적용 + in-memory 단위테스트(미달 hit 제거).
3. `runs.py`: VectorQuery에 min_score 주입.
4. 회귀: `.env` 분리 후 `apps/api` pytest(기본 0.0이라 기존 통과 불변) + ruff.
5. 라이브 보정 스윕 → 기본값 채택 → eval 재측정 → 결과 기록.

## 5. 테스트/검증
- Qdrant 단위테스트: 높은 min_score면 저점수 hit 제거되어 hits 빈다.
- 기존 59 passed 불변(기본 0.0).
- 라이브: 보정 임계값으로 eval → 거부 규율 개선 + useful/citation 유지 확인.

## 6. 영향 파일
`app/core/config.py`, `app/api/v1/runs.py`, `app/infra/qdrant_store.py`, `tests/test_qdrant_store_contracts.py`, (보정 후) `docs/eval-results-live-v0.1.md` 갱신. 프론트 무변경.
