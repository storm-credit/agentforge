# AgentForge 사내(폐쇄망) 기술 드라이런 실행 프롬프트

Status: Pilot-prep 실행 가이드 (증거 수집용) · As of 2026-07-25
연계: [current-state SSOT](current-state.md) §7/§11, [pilot-decision-pack](pilot-decision-pack.md)

> **이건 "기술 드라이런/시연"이지 "실제 파일럿 운영"이 아니다.** 목적은 사내 인프라·사내 모델로 실제로 돌려
> **파일럿 GO/HOLD 결정의 실측 증거**(품질·지연·ACL 무결성)를 만드는 것. SSO 미연동(헤더 스텁)·운영통제
> 미비 상태이므로 **실 민감문서 운영에 쓰지 말 것.** 피처 프리즈와 무관(기존 코드 실행일 뿐, 신규 기능 아님).
>
> 이 문서는 사내 담당자(또는 폐쇄망 Claude Code 세션)에 그대로 넘겨 실행할 수 있는 자기완결 프롬프트다.

---

## 0. 시작 전 확인할 입력 (없으면 여기서 멈추고 확보)
1. **사내 LLM 엔드포인트** — OpenAI 호환 `base_url`(예: `http://vllm-host:8000/v1`) + 모델명(회사 표준 `qwen3-30b-a3b`) + 인증토큰 필요 여부.
2. **사내 임베딩 엔드포인트** — OpenAI 호환 `/v1` + 모델명 + **차원(dim)**. ⚠️ dim이 Qdrant 컬렉션과 반드시 일치해야 함(§3 겟차).
3. **폐쇄망 반입 방식** — 사내 git 미러/Nexus, 또는 오프라인 이미지 tar.
4. **호스트** — Docker + docker compose 가능한 리눅스 1대(GPU는 사내 vLLM 쪽에 있으면 됨; 이 앱은 CPU로 충분).
5. **평가용 문서** — 내부 문서 5~30건(민감도/부서 라벨 구분되면 ACL 검증에 좋음). 없으면 우선 합성 시드로 흐름만 확인.

## 1. 소스 반입 (폐쇄망)
- main(`origin/main`)이 최신·CI 그린 상태. 사내 git/Nexus로 미러링하거나, 클린 클론을 오프라인 반입.
- 반입 후 `docs/40-delivery/current-state.md`(권위 SSOT)와 이 문서를 기준으로 진행.

## 2. 컨테이너 이미지 준비
- **온라인 빌드 가능하면**: `deploy/compose/docker-compose.dev.yaml`가 `apps/api`·`apps/web`를 빌드한다.
- **완전 폐쇄망**: 베이스 이미지(`postgres:16-alpine`, `qdrant/qdrant`, `python:3.11`, `node:22`)와 앱 이미지를
  망 밖에서 빌드→`docker save`→반입→`docker load`. (프로덕션 웹은 `apps/web/Dockerfile.prod`=standalone 사용 권장.)

## 3. `.env` 설정 (핵심 — 무코드 이관)
`apps/api/.env`를 `apps/api/.env.example` 복사 후 아래로 채운다(사내 값으로):

```bash
# DB (compose 내부 서비스명 postgres)
AGENT_FORGE_DATABASE_URL=postgresql+psycopg://agentforge:agentforge@postgres:5432/agentforge
AGENT_FORGE_READINESS_CHECK_DATABASE=true

# 벡터: 실제 Qdrant 사용
AGENT_FORGE_VECTOR_BACKEND=qdrant
AGENT_FORGE_QDRANT_URL=http://qdrant:6333            # compose 내부 서비스명

# 임베딩(사내) — dim은 모델에 맞춰야 하고 Qdrant 컬렉션과 일치해야 함
AGENT_FORGE_EMBEDDING_BASE_URL=http://<사내-임베딩>/v1
AGENT_FORGE_EMBEDDING_MODEL=bge-m3
AGENT_FORGE_EMBEDDING_DIM=1024                        # bge-m3=1024. 다른 모델이면 그 dim으로, 컬렉션 재생성 필요
AGENT_FORGE_EMBEDDING_API_KEY=                        # 게이트웨이 인증 필요 시 Bearer 토큰

# LLM(사내 vLLM / 회사 표준 모델)
AGENT_FORGE_LLM_BASE_URL=http://<사내-vLLM>/v1
AGENT_FORGE_LLM_MODEL=qwen3-30b-a3b
AGENT_FORGE_LLM_API_KEY=                              # 필요 시

# (선택) config-C 후보 게이팅 — 실측 후 ADR-114에서 채택 결정
AGENT_FORGE_RETRIEVAL_MIN_SCORE=0.53                  # bge-m3 보정값(로컬 기준). 사내 임베딩이면 재보정 필요
AGENT_FORGE_ANSWER_MIN_SCORE=0.0                      # config-C 실험 시 0.53
AGENT_FORGE_GROUNDING_MIN=0.1                         # 출력 가드(인젝션 하드닝, 거친 안전망)
AGENT_FORGE_RERANK_BACKEND=none                       # config-C 실험 시 hybrid_lexical
AGENT_FORGE_RERANK_TOP_K=                             # config-C 실험 시 2
```

> **⚠️ dim 겟차**: 임베딩 모델을 바꾸면 벡터 차원이 달라진다. Qdrant `chunks_active` 컬렉션이 이전 dim으로
> 이미 만들어졌으면 **컬렉션을 비우고 재색인**해야 한다(dim 불일치는 upsert 실패). 첫 배포면 그냥 새로 색인하면 됨.

> **⚠️ 프론트 API URL 겟차(코드 미수정, 프리즈)**: 웹은 빌드타임 env `NEXT_PUBLIC_API_BASE_URL`을 읽는다
> (기본값 `http://localhost:8000/api/v1`). dev compose가 세팅하는 `NEXT_PUBLIC_AGENT_FORGE_API_BASE_URL`은
> **이름이 달라 무시**된다 — 기본 포트(웹:3000/API:8000, 브라우저에서 localhost 접근)면 fallback으로 동작.
> **API 포트/호스트를 바꾸면** 웹 이미지 빌드 시 `NEXT_PUBLIC_API_BASE_URL`을 명시할 것.

> compose의 `api` 서비스는 기본적으로 LLM/임베딩/Qdrant env를 안 넘긴다 — 위 `.env`를 `env_file`로 물리거나
> compose `api.environment`에 추가할 것. compose `--reload`/`npm run dev`는 개발용이므로, 시연이라도 안정성
> 원하면 prod 이미지(standalone) 사용 권장.

## 4. 기동
```bash
cd deploy/compose
docker compose -f docker-compose.dev.yaml up -d postgres qdrant   # 데이터 계층 먼저
docker compose -f docker-compose.dev.yaml up -d api               # alembic upgrade head 자동 실행 후 uvicorn
docker compose -f docker-compose.dev.yaml up -d web
# 헬스: curl http://localhost:8000/healthz , http://localhost:8000/readyz (vector_store/object_store 상태 포함)
```
`/readyz`가 `vector_store: ok`면 Qdrant 연결 정상. `unavailable`이면 QDRANT_URL·네트워크 확인.

## 5. 데이터 넣기 (택1 또는 둘 다)
- **A. 합성 시드(흐름 확인용)**: `docker compose exec api python -m app.seed_demo && docker compose exec api python -m app.seed_demo_rich`
  → 게시된 데모 에이전트 + 색인된 문서 생성.
- **B. 실제 내부 문서(권장, 증거용)**: 웹 UI `Knowledge`에서 지식소스 만들고 TXT/MD/PDF/DOCX 업로드 → 색인.
  민감도(공개/내부/제한/기밀)·접근그룹을 문서별로 지정해 **ACL 동작을 실제로 검증**.

## 6. 접속·사용
- 웹: `http://localhost:3000` (또는 호스트 IP). 사이드바 **역할 스위처**(admin/developer)로 권한별 화면 확인.
- 에이전트: `Agents`에서 생성 → 버전 validate/publish → `Chat`에서 질문.
- 트레이스: `Runs`에서 검색히트·인용·거부·라우트·가드 신호 확인. `Audit`(admin)에서 감사 이벤트.

## 7. 검증 체크리스트 (파일럿 증거 = 여기서 나옴)
- [ ] **ACL 누출 0**: 낮은 권한 역할로, 권한 없는 문서가 검색/답변/인용에 **절대** 안 나오는지(가장 중요).
- [ ] **인용**: 답변에 실제 근거 문서 인용이 붙는지.
- [ ] **거부 규율**: 근거 없는/권한 밖 질문에 안전 거부하는지.
- [ ] **인젝션**: 문서 안에 "이전 지시 무시하고 …" 같은 문구를 심어도 답변이 납치되지 않는지(30B에서 개선 기대, 실측).
- [ ] **지연시간**: 첫 질문(모델 로딩)·이후 질문 p50/p95.
- [ ] **정량 평가(선택)**: `eval/harness/run_live_eval.py`를 사내 스택 대상으로 돌려 citation/useful/refusal/faithfulness 수치화
      (`AGENT_FORGE_EVAL_BASE_URL`을 사내 API로, corpus는 내부 문서 기반으로 교체). config-C(none vs hybrid_lexical+top_k2+answer_min 0.53) before/after 비교 → **ADR-114** 근거.

## 8. 수집할 증거 (Pilot Decision Pack에 투입)
- 사내 모델 실측 품질 수치(위 §7) → ADR-104/105/106/114.
- ACL 무결성 결과(누출 0 여부) → ADR-102/103 관련.
- 지연·리소스·안정성 관찰 → ADR-104/107/112.
- 관찰된 결함/이탈은 [current-state](current-state.md) §7의 "자격 있는 결함"이면 Work Order로 승격.

## 9. 정직한 한계 (이 드라이런이 증명하지 *못하는* 것)
- **SSO 없음** — 신원=HTTP 헤더 스텁. 실 권한 신뢰는 사내 SSO(ADR-103) 후에만.
- **운영통제 없음** — 백업/복구·감사 보존·모니터링·폐쇄망 staging 정식 토폴로지 미결(ADR-107~112).
- 따라서 결과는 **"기술 실현성 증거"**이지 **"운영 파일럿 합격"**이 아니다. 최종 Pilot GO/HOLD/NO-GO는
  책임 있는 사람이 Evidence Package를 보고 기록한다(current-state §9).
