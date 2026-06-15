# 라이브 평가: LLM-as-judge 답변가능성 게이트 (2026-06-15)

`cases-live-v0.2.json`(케이스15) · Qdrant+bge-m3 · **judge = 로컬 Ollama `qwen3:1.7b`**.
목적: 거부규율(c07 과답변)을 LLM-judge로 코드만으로 고칠 수 있는지, 그리고 **로컬(낮은 버전) 모델로도
효과가 있어 사내 qwen3-30b-a3b에서 더 나아질 여지가 있는지**를 측정.

## before/after (동일 코드, env `AGENT_FORGE_JUDGE_BACKEND` 토글)

| 지표 | judge OFF (기본) | judge ON (qwen3:1.7b) | 판정 |
|---|---|---|---|
| refusal_discipline% | 66.7 | **66.7** | 변화 없음 — c07 여전히 과답변(judge가 YES로 오판) |
| citation% | 100 | **91.7** | **하락** — 유효 answer 케이스 1건을 judge가 잘못 거부 |
| useful_answer% | 83.3 | 83.3 | 동일 |
| leak_free% | 100 | 100 | 동일(보안 불변) |

## 결론 (정직)
- **로컬 `qwen3:1.7b` judge는 이 문제를 못 고친다.** c07(접근 가능하지만 무관한 문서로 과답변)을 잡지 못했고,
  오히려 정상 답변 하나를 오거부해 citation이 떨어졌다 — 작은 모델이라 판정이 **양방향으로 불안정**.
- 따라서 "작은 모델로 어느 정도 되면 큰 모델로 더 잘 된다"의 **전제(작은 모델로 어느 정도 됨)가 이 모델에선 미성립.**
  사내 qwen3-30b-a3b(instruction-following이 훨씬 강함)에선 개선될 가능성이 크지만 **그것은 미측정**이다.
- **코드(judge 훅)는 유지할 가치가 있다**: 이식 가능한 레버(`llm_gateway.judge_answerable` + `answerability_judge`),
  **기본 OFF라 운영 동작 불변**, qwen3-30b-a3b 가용 시 `.env` 한 줄로 켜서 재측정 가능. 정공법(LLM-judge)의 코드 토대를 깔아둠.

## 함의
- 거부규율의 실질 개선은 여전히 **사내 운영급 모델(qwen3-30b-a3b) 또는 cross-encoder rerank**에 의존(⛔ 모델/인프라).
- rerank는 Ollama가 rerank 엔드포인트가 없어 로컬 검증 불가(별도 reranker 서버 필요). judge는 로컬로 측정은 됐으나 1.7b론 부족.
- 측정값(검색 점수·게이팅·집계)은 결정적이라 본 결론은 신뢰 가능. judge 1회 측정(작은 모델 노이즈 존재).
