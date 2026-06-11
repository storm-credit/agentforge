# AgentForge — 생성 파라미터(temperature/top_p) 통제 설계

- 날짜: 2026-06-11
- 상태: 승인됨 (설계+구현단계 통합 — 소규모)
- 동기: 게이트웨이가 `temperature=0.2` 하드코딩, top_p 미설정. 근거형 RAG의 안전 기본은 유지하되 에이전트별로 bounded 조절·통제·감사 가능하게.

## 1. 결정
- env 기본 + 에이전트 버전 config override. 안전 clamp(temperature 0.0~0.7, top_p 0.1~1.0). 이번 슬라이스는 백엔드+config만(빌더 UI는 후속). generator 트레이스에 사용값 기록.

## 2. 구현 단계 (TDD)
1. `config.py`: `llm_temperature: float = 0.2`, `llm_top_p: float | None = None`.
2. `llm_gateway.py`:
   - 상수 `_TEMP_MIN, _TEMP_MAX = 0.0, 0.7` / `_TOP_P_MIN, _TOP_P_MAX = 0.1, 1.0`.
   - 순수 함수 `clamp_temperature(v) -> float`, `clamp_top_p(v) -> float | None`(None은 그대로).
   - `generate(*, question, context, language, temperature: float = 0.2, top_p: float | None = None)`:
     payload `temperature=clamp_temperature(temperature)`; `top_p`는 값이 있을 때만 `clamp_top_p(top_p)`로 포함.
3. `runs.py`: generate 호출 전 `s=get_settings()`; `gen_temp=clamp_temperature(agent_version.config.get("temperature", s.llm_temperature))`, `gen_top_p=clamp_top_p(agent_version.config.get("top_p", s.llm_top_p))`; generate에 전달 + generator 스텝 `output_summary`에 `temperature`/`top_p` 기록.
4. 테스트: clamp 단위테스트(범위 밖→상/하한, None 유지), 게이트웨이 계약테스트(monkeypatch httpx → payload에 clamped temperature + top_p 포함), 기존 60 passed 무영향(기본 0.2 = 현행).

## 3. 검증
- 게이트웨이/런타임 + 신규 테스트 통과(60+ passed, skip0), ruff 클린.
- 라이브: 에이전트 config에 temperature 넣고 질의 → 트레이스에 기록 확인.
- 안전: 무제한 자유 입력 금지(clamp), 기본 낮은 temp 유지.

## 4. 영향 파일
`app/core/config.py`, `app/services/llm_gateway.py`, `app/api/v1/runs.py`, `apps/api/tests/test_llm_gateway_contracts.py`(+ runs 트레이스 검증). 프론트 무변경.
