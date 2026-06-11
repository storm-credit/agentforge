# CLAUDE.md — AgentForge 작업 지침

사내망용 **통제형 AI 에이전트 빌더 플랫폼**(문서 기반 RAG). 개요·실행은 [ONBOARDING.md](ONBOARDING.md), 설계/계획은 `docs/superpowers/specs|plans/`.

## 작업 운영 규칙 (반드시)

1. **한 슬라이스 단위로 진행**: brainstorming → writing-plans → subagent-driven-development(TDD) → finishing-a-development-branch(push + PR + merge). 슬라이스는 작게, 백엔드/프론트 무관 영향 최소.
2. **매 작업(슬라이스)이 끝날 때마다, 턴 마지막에 "다음 작업 핸드오프 프롬프트"를 작성한다.** 새 세션에 그대로 붙여 실행 가능한 자기완결형이어야 하고 다음을 포함:
   - 배경(머지된 PR 요약)·목표·범위(YAGNI)·완료 기준
   - 활용할 도구: superpowers 스킬 체인, agentmemory MCP(recall/remember), 필요 시 subagent/Workflow 하네스, security-review·requesting-code-review, WebSearch 리서치, eval 하네스 재측정
   - 아래 "환경/겟차" 전부
3. **정직 우선**: 테스트·검증 결과를 있는 그대로. 측정 안 한 건 "안 했다"고. 약점/한계 명시.
4. **품질을 측정으로 입증**: 검색·답변 품질 변경은 `eval/harness/run_live_eval.py`로 before/after 수치. 보안 변경은 라이브 재현 + 가능하면 적대적 스윕.

## 환경/겟차 (로컬, Windows)

- **Python은 반드시 `apps/api/.venv/Scripts/python.exe`** (전역 python은 contract 테스트 silent skip).
- **uvicorn에 `--reload` 없음** → 백엔드 코드 변경 후 반드시 재기동. 라이브가 구버전 응답하면 의심. 포트 8000을 옛 프로세스가 점유하면 새 API가 exit 1 → 기존 python 정리 후 기동.
- **pytest 풀스위트는 `apps/api/.env`를 잠시 옆으로 옮긴 뒤 실행**(실 LLM/DB가 2개 테스트에 새어 실패) → 끝나면 복원. 현재 기준 64 passed / 0 skipped.
- **라이브 스택**: `docker start agentforge-ollama compose-postgres-1 compose-qdrant-1` (볼륨 보존 — 모델 bge-m3/qwen3:1.7b, DB `agentforge_mvp2`, Qdrant `chunks_active` 유지). `.env` = qdrant 백엔드 + bge-m3 + agentforge_mvp2 + `AGENT_FORGE_RETRIEVAL_MIN_SCORE=0.53`.
- **프론트 npx/.bin 셰임 깨짐** → node 직접: dev `node node_modules/next/dist/bin/next dev <apps/web 절대경로> -p 3300`, tsc `node node_modules/typescript/bin/tsc --noEmit`, e2e `node node_modules/@playwright/test/cli.js test`(`PLAYWRIGHT_BASE_URL=http://127.0.0.1:3300`). 화면 캡처는 `.claude/launch.json`(node 직접 설정)으로 `preview_start` → 3300 점유 먼저 비울 것.
- **이관(무코드)**: 임베딩/LLM `base_url·model`을 사내 vLLM/Qwen3.6:35B로, `AGENT_FORGE_QDRANT_URL`만 교체.

## 알려진 한계 (배포 전)
SSO 미연동(헤더 스텁) · 프롬프트 인젝션은 약한 모델서 비결정적 우회(하드닝=베이스라인) · 업로드 TXT/MD만 · `/runs` 등 GET 무인증.
