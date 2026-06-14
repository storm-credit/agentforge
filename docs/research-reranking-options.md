# 리서치 브리프: 리랭킹 / LLM-judge / 사내모델 (결정용, 2026-06-15)

⛔ "사내 35B+cross-encoder → 거부 규율 개선"(WS3) 항목을 **결정 가능 상태**로 만들기 위한 인터넷 리서치.
결정·자격증명·인프라는 조직 몫이지만, 아래 옵션·트레이드오프·추천은 그 결정을 돕기 위한 것.

## 1. 풀어야 할 문제 (우리 측정값)
- `docs/eval-results-live-v0.3.md`: **leak_free 100%(보안 OK)** 인데 **refusal_discipline 66.7%** — 거부 케이스 c07이 *과답변*.
- 정량 확정: c07(top_score 0.587)이 정상답변 c06/c12/c14(0.55~0.57)보다 **벡터 유사도가 더 높다** → **스칼라 점수 게이트(answer_min)로는 분리 불가**.
- 즉 "접근 가능하지만 질문에 실제로는 답 못 하는 문서"를 거르는 **의미 수준 판단**이 필요. 그게 리랭커/LLM-judge.

## 2. 옵션 A — Cross-encoder 리랭커 (질의·문서 쌍 직접 채점)
| 모델 | 크기 | 라이선스 | 한국어 | GPU 지연 | 비고 |
|---|---|---|---|---|---|
| **BGE-reranker-v2-m3** | 경량(m3 계열) | Apache-2.0 | ✅(100+ 언어) | ~50–100ms(T4) | **이미 쓰는 임베더 bge-m3와 동일 계열 → 일관성/검증 쉬움**. 원점수는 임계값 튜닝 필요(우리 min_score 튜닝과 동형) |
| **Qwen3-Reranker** | 0.6B / 4B / 8B | Apache-2.0 | ✅(100+ 언어) | 크기 비례 | **사내 모델이 Qwen3.6 계열 → 에코시스템 정합**. instruction-aware, MTEB 다국어 8B 1위(’25-06). 공식 vLLM 도커/문서 |
| ms-marco-MiniLM-L6-v2 | 초경량 | - | ❌(영어) | <50ms(CPU) | 한국어 부적합 — 제외 |

서빙: **vLLM이 리랭커(cross-encoder Score / Jina·Cohere 호환 Rerank API)를 지원** → 폐쇄망 자체호스팅이 기존 vLLM 계획과 그대로 맞물림. (Ollama는 rerank 미지원 — v0.3에서 확인.)

## 3. 옵션 B — LLM-as-judge (faithfulness/충분성 판정)
- 사내 35B를 **judge**로: "(질문, 검색 컨텍스트)에서 이 문서가 질문에 *실제로* 답하는가?"를 이진+근거로 판정 → 아니면 거부. FaithJudge 등 2025 프레임워크가 이 패턴(질문·컨텍스트·답변→binary+설명).
- 장점: c07 같은 "표면 유사·실질 무답" 정확 차단. 단점: 호출당 LLM 비용·지연, 프롬프트 설계 필요.

## 4. 옵션 C — Query rewrite / HyDE (보조)
- 질의를 검색 친화적으로 재작성/가설답변 생성 후 검색. 리콜↑엔 도움이나 c07(과답변) 직접 해결책은 아님 → **2순위 보조**.

## 5. 추천 (단계적)
1. **1순위: BGE-reranker-v2-m3를 vLLM으로 자체호스팅 → retrieval 후 rerank 단계 추가.** 이유: 임베더와 동일 계열(검증·운영 단순), Apache-2.0, 한국어 OK, 폐쇄망 vLLM 정합. c07의 느슨한 매칭을 낮춰 거부 규율 개선이 기대되는 가장 가벼운 정공법.
2. **2순위: 거부 경계 케이스에 LLM-judge(사내 35B) 게이트** 추가 — rerank 후에도 애매한 top 문서의 충분성 판정. faithfulness 메트릭을 eval에 추가.
3. **3순위: query rewrite** — 리콜 이슈 발견 시.
- 모델 택일이 갈리면: **에코시스템 정합 우선이면 Qwen3-Reranker(4B)**, **경량·임베더 일관성 우선이면 BGE-reranker-v2-m3**. 기본 추천은 후자(가벼움+이미 bge 계열 운용 중).

## 6. AgentForge 코드에 어떻게 붙나 (내가 코드로 가능한 부분)
- 🔧 백로그 4의 **"rerank 인터페이스 스텁"**: `runs.py`의 retrieval(top_k) → **rerank 훅(no-op 기본)** → context. 사내 리랭커 URL이 생기면 `.env`로 켜는 이식 가능 레버(임베딩/LLM 게이트웨이와 동일 패턴).
- eval 하네스에 rerank on/off 비교 + faithfulness 케이스 추가 → before/after 입증.
- **결정 필요(⛔, 조직)**: 어느 모델/크기, GPU 예산, vLLM에 리랭커 추가 배포 — 인프라.

## 7. 한계 (정직)
- 위 수치/추천은 공개 벤치마크·문서 기반. **우리 코퍼스에서의 실제 개선폭은 사내 모델 가용 후 eval 재측정 전엔 미확정.** Qwen3-Reranker 온라인 서빙은 ’25년 중반 일부 버전서 지연 이슈 보고 — 배포 시 vLLM 버전 확인 필요.

## 출처
- [Best Reranker Models for RAG (2026), BSWEN](https://docs.bswen.com/blog/2026-02-25-best-reranker-models/)
- [Top 7 Rerankers for RAG, Analytics Vidhya](https://www.analyticsvidhya.com/blog/2025/06/top-rerankers-for-rag/)
- [vLLM Scoring/Rerank API 문서](https://docs.vllm.ai/en/latest/models/pooling_models/scoring/) · [Rerank API PR #12376](https://github.com/vllm-project/vllm/pull/12376)
- [Qwen3-Reranker vLLM 예제](https://docs.vllm.ai/en/v0.10.0/examples/offline_inference/qwen3_reranker.html) · [Qwen3-Reranker-8B 배포기](https://medium.com/@kimdoil1211/deploying-qwen3-reranker-8b-with-vllm-instruction-aware-reranking-for-next-generation-retrieval-c35a57c9f0a6)
- [Benchmarking LLM Faithfulness in RAG (arXiv 2505.04847)](https://arxiv.org/abs/2505.04847) · [LLM-as-a-judge guide, Evidently AI](https://www.evidentlyai.com/llm-guide/llm-as-a-judge)
