# AgentForge MVP — 직원 채팅 답변 (설계 / Spec)

- 날짜: 2026-06-05
- 상태: 승인됨 (브레인스토밍 → spec)
- 범위: AgentForge 본 프로젝트 (별도 신규 레포 아님)

## 1. 배경 (Context)

AgentForge는 사내(폐쇄망)용 **ACL 인지 RAG 에이전트** MVP다. 백엔드의 어려운 부분(권한 검색·인용·실행 기록)은 Sprint 0/1에서 이미 구현됐다. 현재 런타임 실행(`POST /api/v1/runs`)은 다음 순서로 돈다:

`입력가드 → ACL 검색(FakeVectorStore) → 답변 → 인용검증 → 실행기록`

그런데 "답변" 단계가 `runs.py`의 `_build_synthetic_answer()` — **가짜 플레이스홀더**다. 즉 핵심 가치(질문→근거 있는 답변)가 아직 비어 있다. 이 MVP의 목표는 **그 한 곳을 진짜 LLM(Qwen3) 답변으로 채우고, 최소 채팅 화면을 붙여** "직원이 물으면 권한 지킨 출처 답변을 받는다"를 끝까지 돌리는 것이다.

## 2. 목표 / 비목표

**한 줄 목표:** 직원이 채팅으로 물으면 → ACL 지킨 문서만 근거로 → Qwen3가 **출처를 달아** → 질문 언어(또는 토글)로 답한다. 근거가 없으면 솔직히 거부한다.

**비목표 (YAGNI):**
- 관리자 빌더 UI (에이전트 생성·게시 화면) — MVP에선 시드 1개로 대체, 다음 단계
- 실 SSO/계정 연동 — 사내 이관 시
- 실 임베딩 의미검색 — eval이 필요하다고 할 때까지 fake(단어겹침) 유지
- 외부 SaaS 커넥터 — 폐쇄망 보안상 제외 (내부 문서 수집은 유지)
- 비용/성능 모니터링 대시보드 — 기존 audit/run trace로 충분

## 3. 성공 기준 (측정 가능)

기존 Release Gate 재사용 + eval 하네스로 측정:
- ACL 차단 100% (권한 없는 문서가 결과·답변에 절대 안 나옴)
- 답변에 출처(citation) 포함, 인용검증 게이트 통과
- 권한 있는 근거가 없으면 **거부**(no_context/policy_denied)
- 한국어/영어 질문 모두 해당 언어로 답변
- 로컬(Qwen3-8B)에서 동작 → 사내(Qwen3.6:35B) 이관 후 eval 재검증

## 4. 설계

### 4.1 LLM 게이트웨이 (신규)
`apps/api/app/services/llm_gateway.py`
- OpenAI 호환 채팅 클라이언트 (vLLM/Ollama 공용 `/chat/completions`).
- 환경변수: `LLM_BASE_URL`, `LLM_MODEL`, `LLM_TIMEOUT_SECONDS`.
  - 로컬: `LLM_MODEL=Qwen3-8B`, `LLM_BASE_URL=http://localhost:...`
  - 사내: `LLM_MODEL=Qwen3.6:35B`, `LLM_BASE_URL=<사내 vLLM>` — **코드 변경 없이 env만 교체**
- `health()` 제공. `LLM_BASE_URL` 미설정/연결 실패 시 **기존 템플릿 답변으로 폴백**(오프라인 개발·CI 가능).
- Qwen3 대응: `/no_think` 및 `<think>…</think>` 제거 처리.

### 4.2 답변 생성 (교체)
`apps/api/app/api/v1/runs.py`
- `_build_synthetic_answer()` 호출 지점을 게이트웨이 기반 `generate_answer(question, context_hits, language)`로 교체.
- 프롬프트 규칙(시스템):
  - 제공된 검색 청크(context)만 근거로 사용, 외부지식 금지
  - 답변에 출처(문서/locator) 표기
  - 충분한 근거가 없으면 추측 금지, **거부 메시지**
  - 지정 언어로 답변
- 실패/비활성 시 기존 합성 답변으로 폴백.
- 기존 **인용검증**(`app/domain/citations.py`)과 run/step/retrieval_hit 기록은 그대로 유지.

### 4.3 언어 (자동 + 토글)
- `RunCreate` 스키마에 `language: "auto" | "ko" | "en"` (기본 `auto`) 추가.
- `auto` = 질문 언어 감지(간단 규칙: 한글 포함 여부 등)로 결정.
- `ko`/`en` = 강제. 프롬프트의 답변 언어 지시에 반영.

### 4.4 시드 1개 (빌더 대체)
- 시드 스크립트/마이그레이션으로 **에이전트 1개 + 게시 버전 + 지식소스 + 샘플 문서**(기존 `eval/synthetic-corpus` 활용)를 심는다.
- → 관리자 빌더 UI 없이도 채팅이 즉시 동작.

### 4.5 최소 채팅 UI (신규)
`apps/web` 채팅 페이지
- 구성: 질문 입력창 · 답변 표시 · **출처 목록** · **부서/사용자 모의 선택** · **한/영 토글**.
- 모의 사용자 선택 → `X-Agent-Forge-User/Department/Roles/Groups/Clearance` 헤더로 매핑 → `POST /api/v1/runs` 호출.
- 응답의 answer + citations(RetrievalHit) 렌더.

### 4.6 신원/권한 (모의)
- 로컬 MVP: 화면의 부서/권한 선택이 곧 principal(헤더 기반, 기존 `get_principal` stub 재사용).
- 실 SSO는 사내 이관 시 `get_principal`만 교체하면 됨(나머지 ACL 로직 불변).

## 5. 데이터 흐름

```
부서 선택(모의 신원) → 질문(+언어)
  → POST /api/v1/runs
    → 입력가드
    → ACL 검색(권한 문서만, FakeVectorStore)
    → Qwen3 답변 생성(컨텍스트 한정 · 인용 · 언어 · 근거없으면 거부)
    → 인용검증 게이트
    → run/run_step/retrieval_hit/audit 기록
  → 화면: 답변 + 출처 목록
```

## 6. 모델 / 배포

- 개발: 로컬 Qwen3-8B (Ollama 또는 vLLM, OpenAI 호환).
- 이관: 사내 Qwen3.6:35B (vLLM). **env 교체만, 무코드.**
- 패키징: 기존 Docker compose 활용. 외부 SaaS 호출 0 (폐쇄망 안전).
- 철학: **약한 모델(8B)을 하한선으로 튜닝** → 강한 사내 모델은 업그레이드. 단 이관 후 eval 재검증 필수.

## 7. 변경/생성 파일

| 파일 | 작업 |
|------|------|
| `apps/api/app/services/llm_gateway.py` | 신규 — OpenAI 호환 LLM 게이트웨이 + 폴백 |
| `apps/api/app/api/v1/runs.py` | 답변 생성 교체(가짜→Qwen3), language 처리 |
| `apps/api/app/domain/schemas.py` | `RunCreate.language` 추가 |
| `apps/api/app/...` (시드) | 에이전트/버전/지식소스/샘플문서 시드 스크립트 |
| `apps/web/app/(chat)/...` | 신규 최소 채팅 페이지 + 모의 사용자/언어 토글 |
| 환경설정 | `LLM_BASE_URL`/`LLM_MODEL`/`LLM_TIMEOUT_SECONDS` |

## 8. 검증

- `apps/api` pytest (Python 3.11 venv) — runs 파이프라인 계약 + 폴백 동작.
- LLM 게이트웨이 단위 테스트(모킹) + 폴백 경로.
- eval 하네스로 ACL/인용/거부/언어 품질 측정 (8B 기준 튜닝, 35B 재검증).
- 로컬에서 채팅 화면으로 한/영 질문 수동 확인.

## 9. 리스크 / 오픈 이슈

- fake(단어겹침) 검색이 8B에서 답 품질을 떨어뜨릴 수 있음 → eval 점수로 판단, 나쁘면 실 임베딩 추가(별도 작업).
- 회사 자체/도입 모델 유무 미확정 → 있으면 게이트웨이에 후보로 추가(엔드포인트만).
- 언어 자동감지 규칙의 정확도(혼합 언어 질문) → 토글로 보완.
