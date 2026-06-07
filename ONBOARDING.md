# Agent Forge — 온보딩 가이드

사내망용 **통제형 AI 에이전트 빌더 플랫폼**. 승인된 모델·사내 문서·권한정책·감사 로그를 조합해 업무용 AI 에이전트를 만들고 운영한다. 1차 MVP는 **사내 문서 기반 RAG**다.

## 지금 동작하는 한 바퀴 (MVP)

문서 올리기 → 에이전트 만들기 → 출처 달린 답변 → 실행 트레이스 확인. 권한(ACL)에 따라 같은 질문에도 답이 갈린다.

| 화면 | 경로 | 하는 일 |
|---|---|---|
| Chat | `/chat` | 질문 → 권한 있는 문서만 검색해 출처 달린 한/영 답변, 없으면 거부 |
| Agents | `/agents`, `/agents/new` | 에이전트 생성 → 지식소스 연결 → 게시 → 인라인 테스트 |
| Knowledge | `/knowledge` | TXT/MD 업로드·붙여넣기 → bge-m3 임베딩 색인 |
| Runs | `/runs` | 단계 트레이스(검색→생성→검증)·검색 근거(점수·본문·ACL)·거부/강등 사유 |

## 아키텍처

```
Next.js(App Router)  →  FastAPI  →  PostgreSQL (메타/실행 로그)
   apps/web              apps/api      Qdrant     (벡터검색, ACL payload 필터)
                                       임베딩/LLM = OpenAI 호환 엔드포인트(env 주입)
```

- **검색**: 쿼리 임베딩 → Qdrant ANN + **ACL을 쿼리 조건으로** 적용(권한 밖 청크는 LLM 컨텍스트에 못 들어감) + 사후 불변식 재검증.
- **답변**: 컨텍스트만 근거(외부지식 금지), 출처 필수, 권한 문서 없으면 거부.
- **이관(무코드)**: 임베딩/LLM의 `BASE_URL`·`MODEL` env만 사내 vLLM/Qwen3.6:35B로 바꾸면 됨.

## 로컬 실행 (요지)

권장: 전체 스택 compose.

```bash
# 1) 인프라 (postgres / qdrant / minio)
docker compose -f deploy/compose/docker-compose.dev.yaml up -d postgres qdrant
# 2) 모델 서빙 (예: Ollama; 사내선 vLLM)
#    LLM + 임베딩 둘 다 OpenAI 호환 /v1 필요. 예: ollama + qwen3 + bge-m3
# 3) API (apps/api)  — 반드시 .venv 사용(전역 python은 contract 테스트 skip)
#    .venv/Scripts/python -m alembic upgrade head
#    .venv/Scripts/python -m app.seed_demo_rich      # 데모 데이터(소스2·문서4·에이전트)
#    .venv/Scripts/python -m uvicorn app.main:app --port 8000
# 4) Web (apps/web)
#    npm run dev          # → http://localhost:3000
```

`apps/api/.env` 예시(로컬, gitignore됨):
```
AGENT_FORGE_DATABASE_URL=postgresql+psycopg://agentforge:agentforge@localhost:5432/agentforge
AGENT_FORGE_VECTOR_BACKEND=qdrant
AGENT_FORGE_QDRANT_URL=http://localhost:6333
AGENT_FORGE_EMBEDDING_BASE_URL=http://localhost:11434/v1
AGENT_FORGE_EMBEDDING_MODEL=bge-m3
AGENT_FORGE_EMBEDDING_DIM=1024
AGENT_FORGE_LLM_BASE_URL=http://localhost:11434/v1
AGENT_FORGE_LLM_MODEL=qwen3:1.7b
AGENT_FORGE_CORS_ORIGINS=["http://localhost:3000"]
```
- `VECTOR_BACKEND` 기본값은 `fake`(키워드) — env로 `qdrant` 켜야 진짜 의미검색.
- 인증은 현재 **헤더 스텁**(operator/mock 사용자). 실제 SSO는 배포 전 작업.

## 데모 해보기

`/knowledge`에서 문서 추가 → `/agents/new`에서 그 소스 연결·게시 → 테스트 패널에서 질문 → `/runs`에서 트레이스 확인. 데모 시드의 **"외부 반출 보안 절차"(제한)** 는 Operations 사용자만 답을 받고 Finance는 거부됨 — ACL 시연.

## 테스트

```bash
cd apps/api
# .env가 있으면 실LLM/실DB가 일부 테스트에 새므로, 풀 스위트는 .env를 잠시 옆으로:
#   mv .env .env.live ; .venv/Scripts/python -m pytest -q ; mv .env.live .env
.venv/Scripts/python -m pytest -q          # 백엔드 (현재 58 passed)
cd ../../eval/harness && python -m pytest tests   # eval 하네스
cd ../../apps/web && npx playwright test    # 프론트 렌더 스모크
```

## 더 읽을 것

- 설계/계획: `docs/superpowers/specs/`, `docs/superpowers/plans/`
- 제품 문서: `docs/` (architecture, rag-design, security-model, mvp-scope, implementation-backlog)

## 알려진 한계 / 다음

- 인증: SSO 미연동(헤더 스텁) — 배포 전 필수.
- 문서: TXT/MD만. PDF/DOCX 파싱 + MinIO 원본 저장은 다음 슬라이스(파서가 mime별 교체 구조라 확장 용이).
- `/runs` 등 GET은 현재 무인증 — SSO 도입 시 principal 스코프 제한 필요.
