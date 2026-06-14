# AgentForge — 거부 규율 + ACL 지표 분리 설계

- 날짜: 2026-06-14
- 상태: 승인됨 (사용자가 경로 선택 + 자율 진행 위임)
- 동기: v0.2 측정에서 `acl_pass%`가 **보안(누출)** 과 **거부 규율(과답변)** 을 뭉쳐 오해를 유발. 실제 누출은 0건인데 c07 과답변 1건이 acl_pass를 93.3%로 깎음. 또 리랭킹은 사내 cross-encoder 가용 시로 이월(Ollama가 rerank 미지원 확인). 모델 없이 지표를 정직화하고 거부 규율 레버를 마련한다.

## 1. 결정
- (a) **지표 분리**(eval 스코어러): `leak_free_pct`(전 케이스 no_leak — 보안 핵심) + `refusal_discipline_pct`(policy_denied/refuse 케이스의 behavior_ok — 과답변 안 함). `acl_pass_pct`는 호환 위해 유지(=no_leak ∧ deny_ok).
- (b) **답변 확신 게이트**(런타임): `answer_min_score`(env `AGENT_FORGE_ANSWER_MIN_SCORE`, 기본 0.0=off). top 벡터 점수 < answer_min이면 LLM 호출 없이 거부(`_guard_refusal`, 인용 비움). `retrieval_min_score`(컨텍스트 진입 0.53)와 **분리**된 "답변 확신" 게이트.
- (c) **정직한 음성 결과**: v0.2로 보정 시 c07(0.587)이 정상-약매치 c06(0.558)·c14(0.554)와 점수대가 겹쳐 **단일 임계로 분리 불가**임을 데이터로 입증 → 거부 규율의 정밀 개선은 rerank/LLM-judge가 정공법임을 정량 근거화. 기본 off 권장.

## 2. 변경
### 스코어러 `eval/harness/agentforge_eval/live_scorer.py`
- `aggregate()`에 `leak_free_pct`, `refusal_discipline_pct` 추가.
  - leak_free = no_leak True 비율(전 케이스). deny_cases = behavior ∈ {policy_denied, refuse}. refusal_discipline = deny_cases 중 behavior_ok True 비율(분모 0이면 100).
- 케이스 행에는 기존 필드 유지(스키마 불변). 집계만 확장.

### 런타임 `apps/api/app/api/v1/runs.py`
- 검색 후 `top_score = max((h.score for h in hits), default=0.0)`.
- `answer_min = gen_settings.answer_min_score`. `confidence_ok = top_score >= answer_min`.
- `confidence_ok`가 False면: LLM 생성 건너뛰고 `run.answer=_guard_refusal(lang)`, `citations=[]`, generator step mode="refused"(confidence_gate), guard_output에 `confidence_gate_tripped=True`, `top_score` 기록. citation_validator는 기존대로(citation_required면 fail→status=failed; 거부이므로 빈 인용 정상).
- `confidence_ok`가 True면: 기존 생성 + grounding 가드 경로 그대로.

### 설정 `apps/api/app/core/config.py`
- `answer_min_score: float = 0.0` (주석: top 점수가 이 값 미만이면 답변 대신 거부; retrieval_min_score와 분리된 확신 게이트).

## 3. 테스트 (TDD)
- 스코어러 단위테스트: 누출 0·거부 미스 1 케이스 묶음 → leak_free=100, refusal_discipline<100, acl_pass<100 동시 확인. 거부 케이스 없을 때 refusal_discipline=100.
- 런타임 계약테스트: answer_min을 높게 설정(상위 점수 미만)하면 거부(인용 0, LLM 미호출=fallback/refused, guard_output confidence_gate_tripped True). 기본 0.0이면 기존 동작 불변(회귀 없음).
- 풀스위트 그린(.env 옆으로; baseline 80). ruff 클린.

## 4. 검증 (라이브, v0.2)
- run_live_eval(AGENT_FORGE_EVAL_CORPUS=cases-live-v0.2.json)로 answer_min 0.0(off) 측정 → 새 지표(leak_free/refusal_discipline) 보고.
- answer_min을 0.56·0.60·0.62로 스윕 → c07 거부 여부 vs c06/c14 정상답변 손실을 표로. **임계 분리 불가**를 수치로 확정.
- docs/eval-results-live-v0.3.md: 지표 분리 결과 + answer_min 스윕 + "단일 임계로 c07/c06 분리 불가 → rerank/LLM-judge 필요" 결론.
- 보안 영향: ACL/payload 불변(거부는 더 보수적 방향). 누출 0 유지 확인.

## 5. 영향 파일
`eval/harness/agentforge_eval/live_scorer.py`(집계 2지표), `eval/harness/tests/test_live_scorer.py`(테스트), `apps/api/app/core/config.py`(필드), `apps/api/app/api/v1/runs.py`(확신 게이트+트레이스), 런타임 계약테스트, `docs/eval-results-live-v0.3.md`.

## 6. 범위 밖 (후속)
리랭킹(사내 cross-encoder 가용 시) · LLM-judge faithfulness · 하이브리드 검색.
