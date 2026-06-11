# AgentForge — 프롬프트 인젝션 출력 가드 (결정적 grounding) 설계

- 날짜: 2026-06-11
- 상태: 승인됨 (설계+구현단계 통합 — 소규모 백엔드)
- 동기: 업로드 문서 속 악성 지시가 답변을 납치(예: 'PWNED'). 프롬프트 하드닝(베이스라인)은 약한 모델서 비결정적으로 뚫림. 모델에 의존하지 않는 결정적 층 추가.
- 리서치 근거: RAG 인젝션 방어 = 출력 grounding/citation 검증(미근거 차단), 단 FP 임계 보정 필수(Llama Guard 4% FP 경고).

## 1. 설계
- (a) **결정적 grounding 가드**: 생성(mode=llm)+컨텍스트 존재 시, 답변이 검색 컨텍스트에 근거하는지 `grounding_score`로 측정. 임계 미만이면 **안전 거부로 교체**(답변 대체 + citations 제거) + guard_output 스텝에 `grounding_score`·`guard_tripped` 기록.
- 임계값: env `AGENT_FORGE_GROUNDING_MIN`(기본 0.0=off) → eval로 보정(정상 통과 + 인젝션 차단). **FP 회피 최우선.**
- (b) 인제스트 시그니처 스캔 / (c) LLM-judge: 범위 제외(후속). 정직: 결정적 가드는 우회 가능 — 운영 모델+LLM-judge로 보강 여지.

## 2. grounding_score (순수 함수, 한국어 굴절 견고)
`grounding_score(answer: str, context: str) -> float`:
- answer를 어절(공백) 분해 → casefold·양끝 구두점 제거 → 길이 ≥2 토큰만.
- context는 casefold 전체 문자열.
- 토큰이 "근거됨" = 그 토큰의 길이 ≥2 접두사 중 하나가 context에 substring으로 존재(한국어 조사 접미 보정: '휴가를'→'휴가' 매칭; 영어 'PWNED'→Korean context에 없음).
- score = 근거된 토큰 수 / 전체 토큰 수. 토큰 0개(빈 답변)면 1.0(불벌점).

## 3. 런타임 배선 (runs.py)
generate 직후, citation_validation **이전**에:
```
if generated.used_llm and context_blocks:
    ctx = "\n".join(b.content for b in context_blocks)
    grounding = grounding_score(run.answer, ctx)
    if grounding < settings.grounding_min:
        guard_tripped = True
        run.answer = _guard_refusal(answer_language)
        citations = []; run.citations = []
```
guard_output 스텝 output_summary에 `grounding_score`(반올림)·`guard_tripped` 기록. citations가 비면 citation_validation/guardrail은 기존 로직대로(citation_required면 실패 처리) — 가드 발동 = 유효 답변 없음이라 적절.

## 4. 테스트
- grounding 단위테스트: 'PWNED' vs 한국어 컨텍스트→낮음; 정상 답변(컨텍스트 어절 포함)→높음; 빈 답변→1.0; 굴절('휴가를' vs '휴가')→근거됨; 경계.
- 런타임: grounding_min 높게 monkeypatch → 인젝션류 답변이 거부로 교체되고 guard_tripped 기록(가짜 게이트웨이로).
- 기존 64 passed 무영향(기본 0.0=off).

## 5. 보정·검증
- eval cases-live-v0.1에 인젝션 케이스 추가 → run_live_eval.py를 grounding_min 0.0/보정값으로 → 인젝션 차단율·정상 무차단(FP 0) before/after → docs/eval-results 갱신.
- security-review 스킬, PR 전 requesting-code-review.

## 6. 영향 파일
신규 `app/domain/grounding.py` + 테스트, 수정 `app/api/v1/runs.py`(배선·guard refusal·트레이스), `app/core/config.py`(grounding_min), eval 케이스/문서. 프론트 무변경.
