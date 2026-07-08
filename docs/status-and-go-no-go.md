# AgentForge 현재 상태 ↔ WBS 정합 + Go/No-Go (2026-06-15)

`notes/01_PM/WBS.md`는 **원래 계획 기준선**(상태 칸 대부분 `대기`)이라 실제 진행과 어긋난다.
이 문서가 **현재 실제 상태**의 단일 출처다. 근거 = git PR(#1~#24)·`docs/superpowers/specs|plans/`·
`docs/eval-results-live-v0.*`·코드.

## 한 줄 요약
**MVP 코드와 8주 품질 게이트는 사실상 달성**(권한 기반 RAG Q&A가 인용·ACL·감사와 함께 E2E 동작,
eval에서 citation 100% / useful 83.3% / leak 0건). **남은 것은 거의 전부 조직·인프라 결정 대기**
(파일럿 부서·실문서·SSO·폐쇄망·사내모델). 즉 **프로젝트는 코드가 아니라 "결정"에 막혀 있다.**

## WBS 워크스트림별 실제 상태

범례: ✅ 완료(코드/문서 존재·검증) · 🟡 부분 · ⛔ 조직/인프라 결정 대기(코드 불가) · 🔧 코드로 닫을 수 있으나 미구현

### WS1 PM/기획
| 항목 | 상태 | 근거 |
|---|---|---|
| 프로젝트 제안서·개요·MVP 범위·유스케이스 | ✅ | `docs/project-proposal.md`, `mvp-scope.md`, `use-case-definition.md`, `notes/00_Project/*` |
| 구현 착수 Backlog | ✅ | `docs/implementation-backlog.md`, `notes/01_PM/구현 착수 Backlog.md` |
| Stakeholder Map / 파일럿 결과 보고 | ⛔ | 이해관계자·파일럿 미확정(조직) |

### WS2 보안/권한
| 항목 | 상태 | 근거 |
|---|---|---|
| ACL Matrix / Threat Model / 감사 정책 | ✅(문서) | `notes/05_Security/*` |
| 검색 전 ACL 필터 | ✅ | in-query Qdrant payload 필터 + 재검사 (`qdrant_store.py`), 권한 회수→즉시 제외(PR #21) |
| 문서 ACL 편집·회수 | ✅ | `PATCH /documents/{id}/acl` (PR #21), 라이브 입증 |
| audit log + PII 마스킹 | ✅ | `write_audit_event` 전역, 옵트인 PII 마스킹(PR #24) |
| 보안 차단 테스트(누출 0건) | ✅ | **leak_free 100%** 라이브(v0.3) + 계약테스트 |
| run 조회 인가(타 사용자 trace 차단) | ✅ | GET `/runs`·`/{id}`·`/steps`·`/retrieval-hits`가 owner/admin 스코프(PR #29). 라이브: 일반 0건/admin 전체 |
| 문서목록 GET 메타 스코프 | 🔧 | 미적용(메타만·원문 없음, 빌더 소스픽커 영향) — operator-sees-all 정책 정해지면 |
| 권한 테스트 "실계정" | ⛔ | 현재 헤더 스텁/목 사용자 — 실 IdP 대기 |

### WS3 데이터/RAG
| 항목 | 상태 | 근거 |
|---|---|---|
| 파서/청킹(오버랩) | ✅ | TXT/MD/PDF/DOCX, 청크 오버랩(citation 83→100% 입증) |
| 객체저장소(원본 보관)+재인제스트 | ✅ | MinIO 배선, opt-in(기본 none), 실 MinIO 라이브 검증(PR #30) |
| 임베딩/벡터 색인 | ✅ | Qdrant + bge-m3, `chunks_active` |
| citation 정책 | ✅ | 인용 필수·검증, eval **citation 100%** |
| 평가 질문 세트 | ✅ | `cases-live-v0.1/v0.2`, `eval/harness/run_live_eval.py` |
| **rerank / query rewrite / LLM-judge** | ⛔ | 사내 cross-encoder/qwen3-30b-a3b 필요(Ollama rerank 미지원 확인) — **거부 규율 약점(refusal_discipline 66.7%)의 정공법** |
| 파일럿 실문서 30~100건 | ⛔ | 문서 소유자·부서 대기 |

### WS4 Agent Platform 구현
| 항목 | 상태 | 근거 |
|---|---|---|
| Agent Registry(API/DB) | ✅ | `agents.py`, 버전 라이프사이클 draft→validated→published |
| Model Gateway | ✅ | `llm_gateway.py` OpenAI 호환(env로 사내 vLLM 이식) |
| Runtime Orchestrator | ✅ | `runs.py`: 질문→검색→생성→검증→로그, 트레이스 |
| Agent Studio UI | ✅ | 생성/연결/게시/테스트 + 버전 validate/publish + **새 버전 생성(자동 채번 v2,v3…)** (PR #23, #28) |
| Audit Log | ✅ | 실행/정책 이벤트 기록 |

### WS5 QA/파일럿/운영
| 항목 | 상태 | 근거 |
|---|---|---|
| E2E 테스트 | ✅(코드) | Playwright 14 + 백엔드 128 passed (2026-07-08 기준) |
| 품질 평가 | ✅(MVP 코퍼스) | citation 100% / useful 83.3% — 8주 게이트(95%/80%) 충족 |
| MVP 데모(Go/No-Go) | 🟡 | 코드는 데모 가능 상태, **라이브 데모/판단 미실시**(조직) |
| 파일럿 운영 가이드 / 운영 전환 | ⛔ | 폐쇄망 staging·EP-07 배포 대기(인프라) |

## 4·8·12주 게이트 판정
| 시점 | 기준 | 판정 |
|---|---|---|
| 4주 | 문서 등록·색인·Agent Card 골격 | ✅ 달성 |
| 8주 | 권한 RAG Q&A MVP, citation·ACL·audit E2E | ✅ **코드/eval로 달성**(citation 100%·leak 0·audit). 단 *라이브 데모·실문서*는 미실시 |
| 12주 | 파일럿 결과·v0.2 로드맵 | ⛔ 파일럿 미착수(조직/인프라 결정 대기) |

## 결정 → 해제 표 (프로젝트의 진짜 병목)
| 필요한 결정/입력 | 주체 | 풀리는 것 |
|---|---|---|
| 파일럿 부서 1곳 + 실문서 30~100건 | 경영/PM/문서소유자 | 9~12주 파일럿 전체, 실데이터 품질 측정 |
| SSO IdP 선택(SAML/OIDC) + 자격증명 | 보안/인프라 | 실 인증·권한 신뢰 기반(헤더 스텁 대체), 배포 전 필수 |
| 사내 모델(qwen3-30b-a3b) + cross-encoder 가용 | 인프라/AI | rerank·LLM-judge·query rewrite → **거부 규율 66.7%→개선**, useful 재측정. 옵션·추천: [research-reranking-options.md](research-reranking-options.md) |
| 폐쇄망 staging 환경(EP-07) | DevOps | 실배포·운영 전환 |

## 내가 결정 없이 코드로 닫을 수 있는 것 (🔧)
1. ✅ **버전 자동증가 + "새 버전 생성" UI** (PR #28).
2. ✅ **run 조회 인가(owner/admin 스코프)** (PR #29). (문서목록 메타 스코프는 빌더 영향+정책 미정으로 의도적 보류.)
3. ✅ **MinIO 객체저장소 배선 + 객체스토어 fetch 인제스트(AF-009)** (PR #30). opt-in(기본 none), 실 MinIO 라이브 검증. ([object-storage-af009.md](object-storage-af009.md))
4. ✅ **rerank 인터페이스/스텁** (PR #31) — runs.py rerank 훅(noop 기본, env 게이트), 실제 cross-encoder는 사내 모델 가용 시 연결. ([research-reranking-options.md](research-reranking-options.md))

5. ✅ **롤백 / 버전 config 디프 뷰** (PR #32) — WS4 버전 라이프사이클 완성.
6. ✅ **LLM-as-judge 답변가능성 게이트** (PR #33) — 코드 훅(local Ollama로 동작, env `AGENT_FORGE_JUDGE_BACKEND`, 기본 off). **측정 결과: 로컬 qwen3:1.7b론 거부규율 개선 없음(citation 100→91.7 하락)** → 실질 개선은 사내 qwen3-30b-a3b 대기. 훅은 이식 레버로 유지. ([eval-results-judge-v0.4.md](eval-results-judge-v0.4.md))

### 보안/거버넌스 군집 (전문가 패널 도출, 코드-now)
7. ✅ **mutation 엔드포인트 RBAC** (PR #35) — `enforce_roles`/`PRIVILEGED_ROLES`로 ACL 변경·게시·검증을 admin/platform-admin/knowledge-manager로 제한, 거부 시 `policy.denied` 감사. + 문서 create/upload `confidentiality_level` 검증 추가. 라이브: developer 403 / admin 200.
8. ✅ **감사 조회 API** (PR #36) — `GET /api/v1/audit/events`(필터+페이지네이션), audit-read 전용 역할(admin/platform-admin/security-auditor), 조회 자체 `audit_log.viewed` 감사. 라이브: developer 403/admin 200.
9. ✅ **문서 ACL 편집 UI + 감사 뷰어** (PR #37) — /knowledge 문서별 ACL 표시+편집(reason 필수→PATCH), /audit 스텁→실 뷰어(GET /audit/events, event_type 필터). 라이브: ACL 편집 round-trip + 감사에 document.acl_changed 노출.
10. ✅ **문서 소프트삭제 + Qdrant 퍼지** (PR #38) — `DELETE /documents/{id}`(admin, reason): status=archived(+청크), Qdrant 퍼지(fail-closed), 감사 `document.archived`. 목록·검색·청크 조회에서 제외. 라이브: developer 403/admin archived, preview 1→0.
11. ✅ **문서목록/청크 GET ACL 스코프** (PR #39) — `GET /knowledge/documents`·`/documents/{id}/chunks`가 principal ACL로 스코프(admin 전체, 비admin은 principal_can_access_document). 프론트 목록은 operator 헤더로 전체 유지. 라이브: admin 110 / Finance 83. **→ 보안·거버넌스 군집 5/5 완료.**
   - 후속(🔧 소): `GET /index-jobs/{id}` 무스코프(pre-existing, security-review MEDIUM) — 같은 패턴으로 스코프 가능.
   - 보류(정책): 문서 *생성/업로드* 시 등급 지정의 역할 게이팅(operator-vs-end-user 정책 필요 — SSO기). PATCH(기존 문서 재분류)는 게이팅됨.

### 다음 백로그 (2026-06-15 풀 전문가 패널 6직무 종합 — 보안 군집 완료 후 재실행)
**🐛 정합성 버그:**
- ✅ **force_reindex 시 옛 Qdrant 벡터 미퍼지** (PR #40) — `run_index_job`가 upsert 전 `delete_document`로 문서 벡터 퍼지(첫 색인엔 no-op). 라이브: v1 3청크→v2 force_reindex 1청크 후 Qdrant 포인트 3→1(고아 0). baseline 126.

**🔧 인가 잔여:**
- ✅ **`GET /index-jobs/{id}` 스코프 + `PATCH /agents/{id}` RBAC** (PR #42) — index-job은 admin 또는 문서 `principal_can_access_document`, 미존재 문서는 fail-closed(비admin 거부). PATCH는 `enforce_roles(PRIVILEGED_ROLES)`. 라이브+계약테스트, security-review 고신뢰 발견 0건. baseline 128.
- ✅ **`GET /agents`·`/agents/{id}`·`/agents/{id}/versions` 스코프** (PR #43, 2026-07-08 PM 오케스트라 배치, opus 작성) — 에이전트에 ACL 필드가 없어 게시 상태 기준: 비admin은 published만 목록, 미게시 건은 403 아닌 **404**(존재 자체 은닉), 버전목록은 published/superseded만(draft/validated 미노출). 프론트 4개 GET에 OPERATOR 헤더 추가(빌더 전체뷰 유지). 계약테스트 4종 신규. security-review 고신뢰 발견 0건.
- **잔여**: `GET /knowledge/sources` 여전히 무스코프(의도적 보류 — 소스에 ACL 개념 자체가 없어 별도 정책 설계 필요).
- (MEDIUM, security-review) `POST /agents/versions`도 RBAC 미적용 — draft 생성만 가능(게시는 게이팅됨)이라 즉시 위험은 낮으나 후속 정리 권장.

**✅ 게이트웨이 인증 토큰 배선** (PR #44, 2026-07-08 PM 오케스트라 배치) — `AGENT_FORGE_LLM_API_KEY`/`AGENT_FORGE_EMBEDDING_API_KEY`(기본 None=헤더 없음, 무변경). 설정 시 `Authorization: Bearer` 자동 첨부(generate/judge_answerable/health/embed 전부). `.env.example`을 4줄→32개 필드 전체 문서화로 확장. 테스트 8종(키 있음/없음 × 4개 호출지점). **폐쇄망 모델 cutover 시 "무코드 이관" 전제를 지켜주는 선제 조치** — 실 토큰 검증 게이트웨이 대상 미검증(인프라 필요, 정직 명시).

**✅ guard_input 실체화** (PR #45, 2026-07-08 PM 오케스트라 배치, opus 작성) — 하드코딩 stub(`{"allowed": True, "risk_level": "low"}` 무조건)을 `domain/input_guard.py`의 결정적 규칙 기반 평가로 교체: 제어문자/널바이트 + 영한 인젝션 마커 문구(짧고 명시적으로 low-recall). **로그만, 차단 안 함**(오탐 방지 위해 run은 그대로 진행) — risk_level·마커 레이블만 정직하게 기록, non-low면 `run.input_guard.injection_detected` 감사(원문 미포함). security-review: log-not-block 보존·감사 페이로드 원문 없음·ReDoS 없음·CJK 오탐 없음·실배선 확인, 고신뢰 발견 0건. 실제 인젝션 강건성은 여전히 ⛔ 사내모델 의존.

**✅ QA 게이트 완성 + 코퍼스 확장** (PR #47, 2026-07-08 PM 오케스트라 배치) — `live_scorer.aggregate()`에 `latency_p50_ms`/`latency_p95_ms`(선형보간)·`trace_completeness_pct`(5단계 트레이스 완전성) 신규(미제공 시 `None`, 임의 0/100 아님). 거부군 코퍼스 3→**9케이스**(`cases-live-v0.3.json`, policy_denied 2·refuse 2·인젝션성향 2 추가) — 1건 뒤집힘의 영향이 33%p→11%p로 완화. 훅메틱 테스트 26 passed(0 skipped). **라이브 before/after 실측**: v0.2(3건)→v0.3(9건)로 refusal_discipline **66.7%→88.9%**(신규 6건 전부 통과, 기존 c07 과답변 케이스는 예상대로 여전히 실패 — 정직 보고). 지연시간 p50 1598→1375ms, p95 4129→5058ms(로컬 qwen3:1.7b, 사내모델 아님). `docs/eval-results-live-v0.4.md`.

**통합 검증(2026-07-08, 4개 PR 순차 머지 후 로컬 재확인):** apps/api 풀스위트 **141 passed, 0 skipped**, ruff 클린.

**🔧 측정/무결성 잔여(QA·RAG):**
- rerank `score_rerank` 실신호 배선(현재 no-op만) + `Reranker`가 (hit,score) 반환하도록. (S) · 결정적 retrieval 회귀테스트. (S) · trace_completeness<100% 실전 경로 라이브 미검증(훅메틱만) — 후속.

**🔧 배포(DevOps) — 2건 완료, 잔여:**
- ✅ **게이트웨이 인증 토큰**(PR #44, 위 참조) · ✅ **프로덕션 web Dockerfile**(PR #46, 2026-07-08 배치) — `apps/web/Dockerfile.prod` 신규 추가(멀티스테이지, standalone output, non-root). 기존 dev용 `apps/web/Dockerfile`(감사에서 "없다"고 오판했던 파일, 실은 존재함)과 `docker-compose.dev.yaml`은 무변경. 라이브: 실제 docker build 성공 + 컨테이너 기동 후 HTTP 200 확인. ⚠️ 검증 중 Docker Desktop 엔진 장애로 `docker desktop restart` 실행 — 이 머신의 다른 프로젝트 컨테이너 십여 개가 함께 재시작됨(정상 복구 확인, 사후 보고).
- 잔여: `.env.example` startup 검증(파일 자체는 PR#44에서 완성) · 프로덕션 compose 전체 배선(리버스프록시·env 주입, Dockerfile.prod는 있으나 미연결) · JSON 로깅+request_id 미들웨어 · CI 워크플로.

**✅ 프론트 데모성 완료** (PR #49, 2026-07-08, 세션 한도로 중단됐던 작업을 Fable 모델·고강도로 이어서 마무리) — `/knowledge` 문서별 **보관(archive) 버튼**(reason 입력→admin-gated DELETE) + `/runs`에 **가드레일 신호 배지**(PII 마스킹·인용검증·신뢰도게이트·그라운딩가드·judge/reranker 활성 시). 기존 ACL 편집 폼/패턴과 일관된 스타일. tsc 클린, **실 라이브 스택에서 e2e 16/16 통과**(기존 14 + 신규 2). 최신 main과 충돌 없이 병합. 검증 중 워크트리의 node_modules 정션 대소문자 문제(Next 클라이언트 런타임 중복 번들 → 전 페이지 크래시)를 스스로 발견·수정.

⚠️ **환경 사고 (투명 공개):** 이번 배치 진행 중 `apps/api/.venv`가 완전히 삭제됨(0파일) — 여러 서브에이전트가 격리 워크트리에 venv가 없어 "메인 체크아웃의 node_modules/venv에 임시 디렉토리 정션을 만들고 끝나면 제거"하는 방식을 각자 썼는데, 그 중 하나의 정리 단계가 정션이 아니라 실제 대상 디렉토리 내용을 삭제한 것으로 추정(정확한 가해 에이전트는 특정 못 함). **즉시 복구**: `py -3.11 -m venv .venv` + `pip install -e ".[dev]"` 재설치 → 풀스위트 141 passed, 0 skipped, ruff 클린 확인. 단 `uv.lock` 정확 버전 고정이 아니라 `pyproject.toml` 범위 기준 재설치라 미세한 버전 차이 가능(현재는 동작에 영향 없는 deprecation 경고 1건뿐). **교훈**: 격리 워크트리 에이전트에게 공유 리소스(venv/node_modules) 접근을 위한 디렉토리 정션 트릭을 맡길 때는 "정션 자체만 제거"를 명시적으로 강조해야 함(예: PowerShell `Remove-Item`이 특정 조건에서 정션을 타고 들어가 대상까지 삭제할 수 있음).

**🔧 관측/감사:** request_id·actor_role 감사 필드(정책 필수). (M)

**🔧 인젝션 코드-now(Security):** 실제 guard_input(현재 하드코딩 stub) — 크기제한·제어문자·정규식 마커 탐지 + `prompt_injection.detected` 감사. 실 강건성은 ⛔ 모델. (M)

**🔧 프론트(데모성):** 문서 보관(archive) 버튼(PR#38 백엔드 UI 없음) (S) · /runs guardrail/judge/PII 신호 노출 + /chat 거부 상태 (S/M) · 역할별 UI(RBAC 시연) (M).

**🔧 백엔드 기타:** 에이전트 archive·run list 필터/페이지네이션·index-job 멱등성. (S~M)

> **거부규율(c07) 갱신:** scalar 게이트(v0.3)·로컬 1.7b judge(v0.4) 모두 못 고침. 코드 토대(judge 훅 + rerank 훅)는 깔렸고, 실질 개선은 사내 qwen3-30b-a3b/cross-encoder 대기(⛔ 모델). rerank는 Ollama 미지원으로 로컬 검증 불가.

## 2026-07-08 PM 오케스트라 종합 점검 (풀 6직무 패널: 보안/RAG/백엔드/프론트/DevOps/QA·PM)

사용자 요청("PM으로써 오케스트라 진행")에 따라 narrow next-slice 선별이 아니라 **전 도메인 개선점/보완점/추가점** 감사를 실시. 병렬 6-에이전트, 각 도메인 read-only. 핵심 교차 발견(2개 이상 직무 수렴)과 도메인별 신규 항목만 기록(중복은 위 섹션에 병합).

### 교차 수렴(3직무 이상 동의 — 최우선 신호)
- **잔여 무스코프 GET(`/agents`류·`/knowledge/sources`)** — 보안·백엔드·프론트 3직무 독립 지적. 프론트는 이 항목이 "역할별 UI(RBAC 시연)"의 **선행 의존성**이라고 명시 — 백엔드가 먼저 닫혀야 프론트가 착수 가능.
- **eval 게이트 미완성(latency/trace-completeness 미측정, deny n=3 통계 취약)** — RAG·QA 양쪽 수렴. QA는 "이게 가장 저비용·고가치, 릴리스 게이트 5개 중 3개가 비어 있어 code-complete 선언이 이르다"고 명시.
- **guard_input이 하드코딩 stub** — 보안·QA 양쪽 지적. 감사로그엔 "검사함"으로 찍히지만 실제 미검사 — 정직성 문제(로그가 거짓 신호).

### 도메인별 신규 발견 (이번 감사 이전 status 문서에 없던 것)
- **보안**: CORS `allow_headers/methods="*"`+credentials 조합 완화 필요, PII 마스킹 기본 off, rate limiting 전무, 세션/재생 방지 없음(헤더 스텁조차 서명·nonce 없음), 보안 응답 헤더(HSTS/CSP 등) 없음.
- **RAG**: 청킹 토큰 근사가 한국어 형태소와 안 맞음(공백분리), XLSX·스캔 PDF(OCR) 미지원, 하이브리드검색(BM25+dense)·쿼리재작성·중복제거·멀티턴 컨텍스트 전무. **qwen3-30b-a3b 확정으로 Qwen3-Reranker/judge 재측정의 우선순위가 추측성에서 "당연히 할 것"으로 격상**.
- **백엔드**: 리스트 엔드포인트 페이지네이션 전무, ACL 필터링이 전체 로드 후 Python 처리(스케일 한계), 인덱스 워커가 동기 인라인(진짜 큐 아님), **소프트삭제가 Document에만 있고 Agent/KnowledgeSource는 hard delete**, `enforce_roles`가 거부 시 자체 커밋 — 향후 호출부가 mutation 먼저 flush하면 부분상태 위험(현재는 안전, 패턴 경고), `readyz`가 Postgres만 체크(Qdrant/객체스토어 미확인), Alembic 3개뿐이고 downgrade 미검증.
- **프론트**: 문서 archive 버튼 없음(백엔드 PR#38엔 있음), `/runs`가 guardrail/judge/PII/rerank 신호를 raw JSON에 묻어둠(안전기능 데모 안 됨), 역할별 UI 없음(모든 mutation 버튼이 무조건 렌더링), retrieval-preview UI 없음(백엔드 존재), 로딩 상태·aria-live·label 접근성 공통 누락, `/eval`·`/admin/settings`는 100% 정적 스텁.
- **DevOps**: **`apps/web/Dockerfile`이 아예 존재하지 않음**(prod 빌드 즉시 실패), 게이트웨이 인증 토큰 배선 없음(Authorization 헤더 자체가 코드에 없음 — 실 vLLM이 토큰 요구 시 "무코드 이관" 전제 붕괴, **가장 시급**), api Dockerfile lockfile·multi-stage·non-root·healthcheck 없음, CI 전무, SBOM/체크섬 자동화 없음(서명키만 진짜 ⛔, 생성 스크립트는 지금 가능).
- **QA/PM**: status 문서 "단일 출처"인데 헤더 날짜(06-15)와 본문 최신성(PR#35~42 소급 반영) 불일치, `useful_answer_pct`가 단일 실행값인데 "충족"으로 확정 표기(v0.3 문서 자체가 "노이즈 있음" 자인), citation_ok이 "인용 존재"만 확인하고 실제 근거(faithfulness)는 미검증, `notes/01_PM/WBS.md` 원안과 이 status 문서의 이원 추적 구조가 계속 부채로 남음.

### QA/PM 종합 판단 (패널 인용)
> "코드 관점 MVP는 사실상 완성되었으나, **측정의 완결성**은 아직 5개 릴리스 게이트 중 3개(latency/trace/거부규율 통계신뢰도)가 비어 있어 QA가 code-complete를 선언하기엔 이르다. 프론트 role-aware-UI는 백엔드 GET-scoping(PR#39 완료분)에 의존했으나 이제 일부 언블록됨 — 잔여 무스코프 GET(agents류)만 닫히면 완전 언블록. PM이 지금 강제해야 할 결정: **코드-now 백로그를 이번엔 QA 게이트 완성(latency/trace 스코어러 + deny 코퍼스 확장)으로 좁히고, 그 다음 잔여 인가(agents/sources GET)로 넘긴다** — 그래야 '코드 완결' 선언 시점이 실제로 방어 가능해진다."

### PM 권고 (전 도메인 종합, 우선순위)
1. **(다음 슬라이스, 최우선)** 잔여 GET 인가(`/agents`·`/agents/{id}`·`/agents/{id}/versions`·`/knowledge/sources`) — 3직무 수렴 + 프론트 역할별 UI의 선행 의존성. S, 이미 검증된 패턴(PR#35~39,42) 재적용.
2. QA 게이트 완성(latency/trace-completeness 스코어러 + deny 코퍼스 n↑) — 릴리스 게이트 정직성 확보, 데이터는 이미 흐름. S~M.
3. DevOps 긴급 2건: `apps/web/Dockerfile` 작성(현재 prod 빌드 불가) + 게이트웨이 인증 토큰 배선(사내 모델 cutover 무코드 전제 보호). 둘 다 S, 인프라 없이 지금 가능.
4. 프론트 데모성(archive 버튼, /runs 신호 노출) — 인가 잔여(1번) 완료 후 착수하면 역할별 UI까지 한 번에.
5. guard_input 실체화 — 보안+QA 수렴, 정직성 문제(로그 거짓 신호) 해소.
- **비코드 불변**: SSO IdP, qwen3-30b-a3b/cross-encoder 실측, 실문서/파일럿 부서, 폐쇄망 EP-07 — 조직 결정 필요.

## Go/No-Go 권고
- **기술 MVP: GO 가능** — 핵심 가치(권한 기반 인용 답변 + 누출 0)가 코드·eval로 성립.
- **파일럿 진입: 조건부 HOLD** — 코드 문제 아님. 위 "결정 → 해제 표"의 4개 입력(파일럿 부서/실문서·SSO·사내모델·폐쇄망)이 채워져야 진입 가능.
- **권고 순서**: (조직) 파일럿 부서·실문서 + SSO 결정 착수 ∥ (코드, 내가 가능) 위 "PM 권고" 1→5 순서.
