# 라이브 평가 결과 — live-v0.5 (2026-07-11): 리랭크 후 top-k 컷오프 + "게이트 완화 + 리랭커" 실험

`cases-live-v0.3.json`(문서11/케이스21) · Qdrant+bge-m3+qwen3:1.7b(로컬 Ollama, 사내 운영 모델 아님). PR #71의 hybrid_lexical 리랭커가 라이브에서 효과 0이었던 근본 원인 2가지(후보 부족 + 컷오프 부재) 중 두 번째를 코드로 닫고, RAG 패널이 제안한 "retrieval_min_score 완화 + 리랭커가 품질 필터" 실험을 실제로 수행.

## 1. 무엇을 추가했나 (코드)

- **`AGENT_FORGE_RERANK_TOP_K`** (신규 설정, `rerank_top_k: int | None = Field(default=None, ge=1)`): 리랭크 이후 상위 K개 히트만 컨텍스트/인용으로 사용. 기본 None = 무제한(기존 동작과 완전 동일, no-op). 0/음수는 Settings 생성 시점에 ValidationError.
- **컷오프 밖 히트도 RetrievalHit 행은 유지**하되 `used_in_context=False`/`used_as_citation=False`로 기록(감사/평가용 "검색됐지만 버려짐" 가시성 보존 — 행을 아예 안 만들면 리랭크가 벡터 1위를 컷오프 밖으로 밀었을 때 eval의 top_score 계산이 달라지고, 게이트 완화 실험에서 무엇이 버려졌는지 볼 수 없음).
- 컷오프 활성 시에만 retriever 스텝 trace에 `rerank_top_k`/`context_hit_count` 기록(기본값에선 trace도 기존과 동일).
- 테스트 +12 (config 검증 7, 런타임 파이프라인 5 — 기본값 무변경 가드 both backends, 컷오프 동작, top_k>히트수 no-op). 풀스위트 215 passed / 0 skipped (baseline 203), ruff 클린.

## 2. 라이브 실험 (각 조건 1회, C만 2회)

| 조건 | min_score | rerank | top_k | answer_min | refusal | useful | citation | leak_free | faithfulness |
|---|---|---|---|---|---|---|---|---|---|
| A (기준선 재현, 이 코드) | 0.53 | none | — | 0 | 88.9 | 83.3 | 100 | 100 | 100 |
| B (패널 원안) | 0.35 | hybrid | 2 | 0 | **22.2** | 91.7 | 100 | 100 | 90.5 |
| C (B + answer 게이트) | 0.35 | hybrid | 2 | 0.53 | 88.9 | **91.7** | 100 | 100 | 100 |

- **A**: v0.4 기준선(88.9/83.3/100)과 동일 — 새 코드의 기본값이 라이브에서도 no-op임을 확인.
- **B (정직한 부정적 결과)**: retrieval_min_score가 사실상 거부 게이트를 겸하고 있어서, 0.35로 낮추면 거부해야 할 9케이스 중 7건이 약하게 관련된 접근가능 청크로 과답변(88.9→22.2). 리랭커+컷오프는 "무엇을 인용할지"만 제어하고 "답변할지 말지"는 제어하지 못한다.
- **C (개선 확인)**: answer_min_score=0.53으로 거부 게이트를 분리 유지하면 refusal 88.9 그대로 + useful_answer 83.3→91.7 (+8.4pt, c12_recovery_priority가 유일하게 뒤집힘 — 넓어진 후보 풀에서 리랭크 상위 2개가 더 나은 컨텍스트 제공). 회귀 0. **동일 조건 2회 재실행에서 결과 동일(안정)**.

## 3. 한계 / 정직 단서

- 로컬 qwen3:1.7b 1~2회 측정. 개선 폭은 케이스 1건(12건 중)이며 corpus가 작다 — 사내 모델(qwen3-30b-a3b) 이관 후 재측정 필요.
- c07_export_denied는 여전히 실패(top_score 0.5867 > 0.53이라 스칼라 게이트로 못 잡음, v0.4와 동일 — 시맨틱 judge가 필요한 케이스).
- 실험은 `.env`를 임시로 바꿔 수행했고 종료 후 원복함(현 라이브 기본은 여전히 0.53/none). 조건 C 구성을 기본으로 채택할지는 별도 결정 사항.
