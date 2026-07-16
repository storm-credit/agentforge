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

**✅ 2026-07-08 PM 오케스트라 배치의 1차 패널 권고 5건 전부 완료** (PR #43 GET스코프·#44 게이트웨이토큰·#45 guard_input·#46 web Dockerfile·#47 QA게이트·#49 프론트데모성). 1차 패널 상세 기록은 git history(이 파일의 이전 리비전) 참고 — 아래는 배치 완료 후 재실행한 2차 패널 결과로 대체.

⚠️ **환경 사고 (투명 공개, 이미 복구됨):** 배치 진행 중 `apps/api/.venv`가 완전히 삭제됨(0파일) — 여러 서브에이전트가 격리 워크트리에 venv가 없어 "메인 체크아웃에 임시 디렉토리 정션을 만들고 끝나면 제거"하는 방식을 각자 썼는데, 그중 하나의 정리 단계가 정션이 아니라 실제 대상 디렉토리 내용을 삭제한 것으로 추정(가해 에이전트 특정 못 함). `py -3.11 -m venv .venv` + `pip install -e ".[dev]"` 재설치로 즉시 복구, 풀스위트 141 passed 확인. 교훈: 정션 트릭보다 "메인 체크아웃 실행파일 절대경로 직접 호출"이 안전.

## 2026-07-08 (2차) PM 오케스트라 종합 점검 — 배치 완료 후 재실행

CLAUDE.md 규칙 2-c(군집 완료 → 풀패널 재실행)에 따라 6직무 재실행. 입력: 위 배치로 갱신된 이 문서.

### 교차 수렴
- **`readyz`가 Qdrant/객체스토어 미체크** — 백엔드·DevOps 독립 수렴. Postgres만 체크해 벡터스토어가 죽어도 "준비됨"으로 보고.

### 도메인별 핵심 발견
- **보안**: `POST /agents/versions` RBAC 미적용 확인(재확인, S, 최우선). `GET /knowledge/sources`에 **코드-now 부분 해법** 제시 — 전체 ACL 없이도 `confidentiality_rank(clearance) >= confidentiality_rank(source.default_confidentiality_level)`만으로 등급 기준 필터 가능(그룹/부서 ACL까지는 아니지만 "무스코프"보다 확실히 나음). CORS는 이미 origin allowlist라 우려보다 낮은 위험(재평가, 하향).
- **RAG**: **c07 재진단** — 스칼라 게이트(v0.3)·로컬 judge(v0.4) 실패는 환각이 아니라 "정당히 접근 가능하지만 성급한 답변"이 원인 → 추가 스칼라/휴리스틱 땜질은 과적합, 이 스레드는 **문서화하고 닫는 게 맞음**(실 리랭커/judge 대기). 신규: `grounding_score`가 이미 `live_runner.py`에서 계산되는데 `aggregate()`가 안 씀 → **faithfulness_pct 게이트 배선**(S, 완전 결정적, 모델 무관). 신규: **실제 non-LLM 하이브리드(BM25/어휘) 리랭커는 사내모델 없이 지금 만들 수 있음**(M) — 순수 no-op 스텁이 아닌 진짜 신호. rerank 인터페이스에 `score_rerank` 채우는 건 모델 없인 무의미(기각).
- **백엔드**: **문서 archive에 복원(unarchive) API가 없음**(PR#49 프론트 버튼이 노출시킨 비대칭, S, 최우선급) · 리스트 엔드포인트 페이지네이션 전무(M) · `readyz` Postgres만(S) · Agent/KnowledgeSource는 여전히 hard-delete(S~M) · `enforce_roles` 거부시 자체 커밋 패턴 위험 여전(S, 현재는 안전) · Alembic 3개·downgrade 미검증(S).
- **프론트**: **역할별 UI(RBAC 시연)가 이제 진짜 언블록됨** — GET 스코프+RBAC가 이미 서버에서 강제되므로 클라이언트 버튼 숨김은 순수 데모 UX(보안 결정 아님), 착수 가능(M). retrieval-preview UI 미배선(백엔드 존재, S~M). 리스트 검색/필터+로딩상태+접근성 라벨(S, 공통). `/eval`은 아직 이르다(백엔드에 결과 저장 API 자체가 없음 — 새 발견, 배선 말고 백엔드 갭으로 기록).
- **DevOps**: **CI 전무이 1순위** — 이번 venv 사고를 CI(pytest+ruff+tsc on PR)가 있었으면 즉시 잡았을 것(S). startup 설정 검증 없음(S). `Dockerfile.prod`는 여전히 미배선 스캐폴딩(compose 연결 안 됨, M, 급하지 않음). JSON 로깅+request_id 미들웨어(S/M).

### QA/PM 종합 판단 (패널 인용)
> "코드 가능 백로그는 아직 소진 안 됨(CI·trace_completeness 실전검증·faithfulness 게이트 모두 실제 코드-now) — '코드 완결' 아님. 다만 백로그 성격이 **기능 추가에서 안전망 구축(CI·측정 견고화)으로 전환**됐다 — 조직·인프라 벽에 가까워지는 신호. venv 사고는 병렬 멀티에이전트 배치 패턴의 직접적 결과(서브에이전트들이 공유 리소스 정리 방식을 조율 없이 각자 즉흥 처리)."
>
> **운영 권고: 멀티에이전트 "오케스트라 배치" 패턴을 잠시 멈추고, 다음 슬라이스는 CLAUDE.md 규칙 1대로 단일 슬라이스로 진행 — 그 슬라이스가 바로 CI**. 이유: (1) CI가 정확히 이번 venv 사고 같은 걸 자동으로 잡아줄 안전망이니 다음 병렬 배치 *전에* 있어야 함, (2) CI는 본질적으로 순차·인프라성이라 도메인별 병렬화가 안 맞고 집중된 단일 에이전트가 적합, (3) CI가 생기면 배치 모드를 회귀 안전망 있는 채로 재개 가능. 배치 모드는 독립적이고 blast-radius 작은 도메인 슬라이스에 예외적으로 쓰는 것으로.

### PM 권고 (전 도메인 종합, 우선순위)
1. ✅ **CI 워크플로** (PR #53, 2026-07-08, 신규 순차 오케스트레이션 컨벤션 1호 슬라이스, fable-high 작성) — `.github/workflows/ci.yml`: backend job(ruff check + pytest 풀스위트, 3.11), frontend job(npm ci + tsc --noEmit, node 22), concurrency 그룹으로 구버전 실행 취소. 백엔드 스위트는 hermetic(테스트별 in-memory SQLite + FakeVectorStore 기본값)이라 `.env` 없이도 CI에서 그대로 그린. e2e는 라이브 스택 필요해 의도적으로 제외(주석 명시). 로컬 검증(ruff 클린·141 passed·tsc exit 0) + 실 GitHub Actions 그린 런(run 28927570221, backend 30s/141 passed, frontend 25s) 둘 다 확인. **머지 후 로컬 재확인: 141 passed, 0 skipped, ruff 클린.**
2. ✅ **문서 unarchive(복원) API** (PR #55, fable-high) — `POST /documents/{id}/restore`, `archive_document`와 동일한 RBAC(`enforce_roles(PRIVILEGED_ROLES)`)·감사(`document.restored`) 패턴. 설계 상 의도적 이탈: 지시한 "active"가 아니라 **"registered"**로 복원 — `SEARCHABLE_DOCUMENT_STATUSES`(`registered/indexed/ready`) 밖의 "active"는 비admin에게 안 보이고 재색인도 막혀 TDD 중 실패로 발견. 청크는 "active"(목록엔 노출, 벡터 없어 검색은 제외). 벡터는 복원 시 재생성 안 함(아카이브가 퍼지한 걸 복원이 되살리지 않음, 정직하게 docstring 명시) — 검색 가능하려면 기존 `force_reindex` index-job을 별도로 돌려야 함(범위 밖, YAGNI). 테스트 3종(관리자 복원+재노출, 비관리자 403+감사, 비아카이브 409/미존재 404, 벡터스토어 미호출 확인 + 재색인 라운드트립 성공). 프론트는 스킵(아카이브 문서를 보여줄 목록 뷰 자체가 없어 복원 버튼을 붙일 곳이 없음 — 별도 슬라이스 필요, 정직 명시). baseline 144.
3. ✅ **`POST /agents/versions` RBAC + `GET /knowledge/sources` confidentiality_rank 부분 필터** (PR #57, opus, security-review 통과) — `create_agent_version`에 `enforce_roles(PRIVILEGED_ROLES, action="agent_version.create")` 추가(형제 엔드포인트와 동일 배치, 어떤 상태변경보다 먼저). `list_sources`에 `principal` 파라미터 추가, admin은 전체·비admin은 `confidentiality_rank(clearance) >= confidentiality_rank(source.default_confidentiality_level)`만 노출(그룹/부서 ACL은 소스에 필드 자체가 없어 랭크 전용임을 코드 주석에 명시). 프론트 `listSources()`에 OPERATOR 헤더 추가(빌더 소스픽커 전체뷰 유지, tsc 클린). security-review: 고위험 발견 0건, LOW 1건(사전 존재 — `confidentiality_rank()`가 미인식 문자열을 최고등급(confidential)으로 매핑해 리소스엔 fail-closed지만 principal.clearance_level엔 fail-open; 헤더 스텁이라 이미 임의 조작 가능한 값이라 이 PR이 새 노출을 추가하진 않음, SSO 전환 시 함께 정리 권장). 테스트 2종 추가(RBAC 거부+감사, 클리어런스 경계 4단계+admin 우회). baseline 146.
4. ✅ **`readyz`에 Qdrant/객체스토어 체크 추가** (PR #59, sonnet — 순수 인프라) — `check_vector_store()`(`domain/vector.py`)·`check_object_store()`(`infra/object_store.py`) 신규: 각각 실제 백엔드(vector_backend=="qdrant"+embedding_base_url / object_store_backend=="minio")일 때만 클라이언트를 만들어 읽기전용 연결 확인(`get_collections()`/`bucket_exists()`), 아니면 `None`(skipped) 반환 — `get_object_store()`의 버킷 자동생성 부작용을 피하려 별도 client 사용. `/readyz` 응답에 `vector_store`/`object_store` 키 추가(하위호환: 기본 설정에선 기존과 동일하게 전부 skipped), 활성 컴포넌트 중 하나라도 실패하면 503+`degraded`. 테스트 7종(기본 skipped, 각 컴포넌트 실패 시 503, 비활성 시 실제 클라이언트 미생성 확인) 전부 목/몽키패치로 헌메틱(실 Qdrant/MinIO 불필요, 정직 명시). baseline 153.
5. ✅ **`grounding_score` → eval faithfulness_pct 게이트 배선** (PR #61, fable) — `live_scorer.aggregate()`에 `grounding_scores`/`grounding_min` 파라미터 추가, `faithfulness_pct` = 측정된(non-None) grounding_score 중 임계값 이상 비율(백엔드 가드와 동일하게 `>=`). **주의**: 이미 백엔드가 생성 시점에 grounding_min 미만이면 답변을 거부로 치환(guard_tripped)하므로 이 지표는 behavior_ok 중복이 아니라 **가드 발동 전 드리프트를 잡는 선행지표**. 임계값은 신규 env `AGENT_FORGE_EVAL_GROUNDING_MIN`(기본 0.0 = 백엔드 코드 기본값, 실배포 튜닝값 0.1이 아님 — 실 배포 임계값과 맞추려면 운영자가 직접 설정해야 함, 정직 명시). 미측정 시 0/100 아닌 `None`(기존 관례 유지). 하위호환(파라미터 생략 시 기존 호출부 그대로 동작). 테스트 5종. eval/harness 스위트 26→31 passed. **라이브 재측정은 미실시**(순수 집계 로직 변경, 유닛테스트로 검증) — 정직 명시.
6. ✅ **역할별 UI(RBAC 시연)** (PR #63, fable — 오케스트레이터가 세션 한도로 중단된 서브에이전트의 스테이징된 작업을 이어받아 완료) — 데모 역할 스위처(admin/developer, `lib/demoRole.ts`+`RoleSwitcher.tsx`) 추가, `api.ts`의 하드코딩 OPERATOR 상수를 호출시점 `roleHeaders()`로 전면 교체(약 20개 호출부). Knowledge 페이지 ACL편집/보관 버튼, Agent 상세 페이지 버전생성/validate/publish 버튼을 비특권 역할에서 숨김(순수 UX — 서버는 이미 항상 강제). 신규 e2e(`demo-role.spec.ts`)로 서버측 실제 필터링 검증(developer clearance="internal"이라 confidential/restricted 문서는 목록에서 실제로 사라짐, public은 유지). **오케스트레이터가 머지 전 발견·수정한 버그**: 서브에이전트가 남긴 초안 테스트는 "internal" 문서가 사라진다고 가정했으나 developer의 clearance가 "internal"(랭크 동일)이라 실제로는 사라지지 않는 모순 — "restricted"(랭크 상위)로 수정 후 라이브 재검증. tsc 클린, e2e 17/17 라이브 통과(실 API+Postgres+Qdrant). 프론트 스코프: Knowledge·Agent 상세만 커버(감사 뷰어 등은 미포함, 정직 명시). apps/api 미변경(153 그대로).

**🎯 2026-07-08 PM 권고 6건 전부 완료.** 아래 "다음 백로그" 섹션 참고 — 패널을 재실행해 다음 우선순위를 도출할 차례.
- **c07 스레드**: 공식 종결 — 추가 스칼라 땜질 금지, 사내모델/실 리랭커 대기로 문서화.
- **비코드 불변**: SSO IdP, qwen3-30b-a3b/cross-encoder 실측, 실문서/파일럿 부서, 폐쇄망 EP-07 — 조직 결정 필요.

## 2026-07-08 순차 오케스트레이션 컨벤션 (CLAUDE.md 2-d, 사용자 확정)
CI 부재로 인한 병렬배치 venv 사고 이후, 백로그 실행 방식을 **순차 단일 슬라이스(Workflow 단일 트랙) + 모델 배정(기본 Fable, 보안/인가는 opus)**으로 고정. 슬라이스 1건(CI)이 이 컨벤션의 첫 적용 사례이며 앞으로 모든 슬라이스가 이 패턴을 따른다. 각 슬라이스: 에이전트가 PR 오픈까지만 진행 → 오케스트레이터가 diff 검토(보안 슬라이스는 security-review) 후 직접 머지 → 로컬 재검증 → status 문서 갱신(브랜치+PR) → 다음 슬라이스.

## 2026-07-08 (3차) PM 오케스트라 종합 점검 — 6/6 완료 후 재실행

CLAUDE.md 규칙 2-c(항목 소진 → 풀패널 재실행)에 따라 6직무 재실행. 입력: 2차 패널 6건 전부 완료 후의 이 문서 + 실제 코드 재검증.

### 🚨 신규 발견 — 보안 취약점 (최우선, 즉시 수정 대상)
**`POST /documents/{id}/index-jobs` · `POST /index-jobs/{id}/process`에 ACL/RBAC 체크 전무** (`apps/api/app/api/v1/knowledge.py` `create_index_job`/`process_index_job`) — 형제 엔드포인트인 `get_index_job`·`list_document_chunks`는 `principal_can_access_document`로 스코프되는데 이 둘만 누락. 결과: 낮은 clearance의 임의 principal이 자신이 읽을 권한도 없는 **confidential/restricted 문서의 document_id를 지정**해 `force_reindex: true` + 임의 `source_text`로 POST하면, `run_index_job`이 그 문서의 **실제 벡터를 퍼지하고 공격자가 넣은 텍스트로 재색인**하되 문서의 기존(고등급) confidentiality/access_groups 태그는 그대로 유지 — 이후 정당한 고권한 사용자가 조작된 내용을 신뢰된 인용 답변으로 받는 **콘텐츠 포이즈닝/무결성 우회**(읽기 권한조차 필요 없음). 인용 신뢰라는 플랫폼 핵심 보장을 직접 훼손. 계약테스트도 GET만 커버, 이 두 쓰기 엔드포인트의 인가는 테스트가 없음(확인됨). **다음 슬라이스 최우선, opus 배정.**

### PM 권고 (전 도메인 종합, 우선순위) — 3차
1. ✅ **🚨 index-job 생성/처리 엔드포인트 ACL 추가** (PR #66, opus, security-review 통과) — `create_index_job`·`process_index_job`에 형제 read 엔드포인트(`get_index_job`/`list_document_chunks`)와 동일한 `"admin" not in principal.roles and not principal_can_access_document(...)` 게이트를 어떤 상태변경보다 먼저 추가(403, 이 파일의 기존 관례와 일관). **인가모델 선택**: `PRIVILEGED_ROLES`가 아닌 read-ACL 채택 — `register_document`/업로드가 애초에 RBAC 게이트가 없어 비특권 사용자가 자기 문서를 정상적으로 색인하는 흐름이 있으므로, 특권역할 게이팅은 그 흐름을 깸. 거부 시 감사 없음(형제 엔드포인트와 동일 패턴 유지). 테스트 4종(거부+**퍼지 미발생 증명**·거부+job 상태 불변·정상 인가 회귀없음·admin 우회). security-review: 체크 배치·양쪽 분기 커버리지·`principal_can_access_document`의 fail-closed 특성·테스트의 실질 증명력 모두 확인, 우회 없음. LOW 2건(비차단): job 상태 409 체크가 인가 체크보다 먼저라 job_id를 아는 공격자에게 사소한 정보 누출 가능(job_id는 랜덤 UUID라 실위험 낮음) — 후속 정리 권장. 색인 실패 문서가 admin조차 재색인 불가능해지는 기존(이 PR 이전부터의) 버그 별도 확인(이 PR이 만든 문제 아님, UX 명확성만 변화). **함께 발견(미수정, 범위 밖)**: `register_document`/`upload_document_and_index`/`create_source`에 RBAC 전무 — 다만 이건 "누가 생성 가능한가" 정책 문제지 기존 콘텐츠 무결성 우회는 아니라 이 PR 머지로 핵심 취약점은 완전히 닫힘(security-review 확인). baseline 157.
2. ✅ **`GET /knowledge/documents`에 `include_archived`(admin 전용) 필터 추가** (PR #68, fable) — `include_archived=true`+admin이면 보관 필터 제거, 비admin이면 **조용히 무시**(403 아님, 이 파일의 GET-list 관례인 "조용한 스코핑"과 일관 — ACL이 허용하더라도 보관 문서는 절대 노출 안 함, 적대적 테스트로 명시 검증). 테스트 1종 추가(기본 무변경·admin 전체노출·비admin 무시 3케이스). baseline 158.
3. ✅ **프론트 보관문서 뷰 + 복원 버튼** (PR #69, fable) — `restoreDocument()` 추가(`archiveDocument()`와 동일 패턴, roleHeaders()), Knowledge 페이지에 "보관됨 보기" 토글(isPrivileged 전용) + 보관 행에 "보관됨" 배지·"복원" 버튼(재색인 필요 안내 포함). 신규 e2e로 전체 흐름 검증(아카이브→토글로 재노출→복원→일반목록 복귀, developer 역할엔 토글 자체 안 보임). **오케스트레이터가 머지 전 라이브 재검증**: 서브에이전트는 미머지 백엔드 브랜치로 테스트했으므로, main에 실제 병합된 backend와 함께 재실행(18개 중 17 통과, 1건은 격리 실행 시 통과 확인되어 병렬 워커 간 사전 존재 플레이키로 판정, 이 PR과 무관). e2e 17/17(+플레이키 1 무관).
4. ✅ **비-LLM 하이브리드(BM25/어휘) 리랭커** (PR #71, fable) — **패널의 "드롭인 가능" 전제가 틀렸음을 구현 중 확인**: `VectorHit`엔 청크 본문이 없고 본문은 리랭킹 이후 단계(`_load_context_blocks`)에서 별도 조회됨 → `runs.py`에서 리랭킹 *전에* chunk_id→content 맵을 한 번 가져와 재사용하도록 배선 변경(중복 쿼리 없음). `HybridLexicalReranker`: BM25(k1=1.5, b=0.75, 요청 내 hit셋 기준 IDF) + RRF(k=60)로 벡터랭킹과 어휘랭킹 융합, opt-in(`AGENT_FORGE_RERANK_BACKEND=hybrid_lexical`, 기본 none 무변경). 부산물로 `rank_original`이 실제로는 리랭킹 *이후* 순서로 잘못 기록되던 잠재 버그도 함께 수정. 테스트 7종(결정성·엣지케이스·전체파이프라인 통합 포함). **라이브 before/after 실측**(v0.3, 실 스택): citation 100/useful 83.3/refusal_discipline 88.9 — **모든 지표 완전 동일**(정직 보고, 개선 없음). 근본원인 확인(추측 아님): `RETRIEVAL_MIN_SCORE=0.53` 게이트 때문에 실제 hit셋 크기가 0~2개뿐이라 RRF가 재정렬할 후보가 부족 — min_score=0으로 낮춘 별도 라이브 프로브로 재정렬 자체는 정상 작동함을 입증(랭크4→랭크3 승격 확인). c07은 여전히 실패(예상대로, 재정렬로 못 고치는 정책성 과답변). baseline 165.
5. ✅ **시작 시 설정 검증(fail-fast)** (PR #73, sonnet) — 4개 백엔드 필드를 `Literal[...]`로 전환(오타/대소문자 실수를 `Settings()` 생성 시점에 즉시 거부) + `model_validator(mode="after")`로 `vector_backend="qdrant"`인데 `embedding_base_url` 미설정이면 명시적 에러(이전엔 조용히 FakeVectorStore로 폴백 → readyz도 "skipped"로 오판하던 바로 그 취약점). `object_store`는 실제 폴백 기본값이 있어 유사 필수화 안 함(실제 코드 확인 후 판단, 억지 규칙 안 만듦). **기존 "미지원 backend는 noop로 폴백" 테스트와의 실제 충돌을 발견·정직 해결**: 삭제하지 않고 부팅 시 거부 테스트 + 이미 생성된 Settings 인스턴스에 직접 attribute 조작(pydantic validation 우회)으로 get_reranker()의 방어적 폴백 분기가 여전히 도달 가능함을 확인하는 테스트로 분리. `get_settings()`가 모듈 임포트 시점에 호출되어 실제 프로세스 부팅 시 실패함을 코드 추적으로 확인(가정 아님). 신규 테스트 21종(`test_config.py`). baseline 187.
6. ✅ **eval 실행결과 영속화 API** (PR #75+#76, fable) — 신규 `EvalRun` 모델+마이그레이션(0004), `POST/GET /api/v1/eval/runs`·`GET /eval/runs/{id}`. **인가 설계**: 쓰기는 `PRIVILEGED_ROLES`(하네스가 operator로 호출), **읽기는 의도적으로 전체 인증 principal에 개방**(audit/events와 달리 PII·보안감사 내용 없는 집계 품질지표라 판단, 근거 명시). 목록은 경량 요약(주요 지표만, cases 배열 제외)·상세는 전체 report. 하네스 연동: `AGENT_FORGE_EVAL_PERSIST=true`(기본 off) opt-in + **fail-soft**(영속화 실패해도 eval 자체는 실패 안 함, stderr 경고만). 프론트 `/eval` 페이지를 정적 스텁("Planned" 하드코딩)에서 실제 이력 테이블로 교체(빈 상태·에러 상태 포함). e2e는 실 라이브 eval 대신 API로 직접 시드 후 렌더 검증(합리적 절충). apps/api 195 passed, eval/harness 41 passed, tsc 클린. 마이그레이션은 스크래치 SQLite로 업/다운그레이드 검증(라이브 Postgres 미검증, 정직 명시).
7. ✅ **`faithfulness_pct` 임계값을 리포트 자체에 노출** (PR #78, sonnet) — `aggregate()`가 `faithfulness_threshold`(실사용 grounding_min, explicit param든 env 폴백이든)를 리포트에 추가, `faithfulness_pct`가 None이어도 항상 존재. 범위를 하네스에 그치지 않고 백엔드 `EvalRunSummary`/`GET /eval/runs` 요약과 프론트 `/eval` 테이블("100.0% (≥0.5)" 형태)까지 자연스럽게 확장(작은 추가라 판단, 정당). eval/harness 41→44 passed, apps/api 195 유지(기존 테스트 확장만), ruff/tsc 클린.
8. ✅ **목록 엔드포인트 페이지네이션** (PR #80, fable) — `list_agents`/`list_sources`/`list_documents`에 `limit`(기본 200, 1~500)/`offset`(기본 0) 추가, `list_audit_events`와 동일한 Query 관례. **정확성 함정 정확히 처리**: `list_agents`는 SQL WHERE만 있어 SQL레벨 LIMIT/OFFSET 안전, 반면 `list_documents`/`list_sources`는 비admin ACL/clearance 필터가 Python에서 사후 적용되므로 **필터 이후 Python에서 슬라이싱**(SQL 레벨로 하면 비admin 페이지가 필터링 전 상위집합 기준으로 잘려 얇아지고 건너뛰는 실제 버그 발생) — 이 트레이드오프(전체 필터셋을 매 요청 서버측에서 여전히 계산) 코드 주석+PR에 정직 명시, 향후 규모 커지면 재검토 권고. **적대적 테스트로 함정 검증**: hidden/visible 문서·소스를 교대로 배치해 비admin의 limit=1 페이지들을 이어붙이면 정확히 필터된 전체 집합과 일치함을 증명 + **실제로 구현을 일부러 깨서(SQL 사전필터로 바꿔) 테스트가 실패하는 것까지 확인 후 원복**(뮤테이션 테스트). 응답 형태는 그대로(bare list, total-count 래퍼 없음 — 의도적 범위 축소, 문서화). baseline 198. **→ 3차 패널 8개 항목 전부 완료.**
- Agent/KnowledgeSource hard-delete: 현재 Agent DELETE 엔드포인트 자체가 없어 활성 위험 아님(잠재적, 급하지 않음).
- Alembic downgrade 미검증: S, 급하지 않음.
- **QA/PM 종합 판단**: 코드-now 백로그 소진 안 됨, "코드 완결" 선언 금지. 다만 성격이 기능→안전망에서 이제 **버그 수정+측정 정합성**으로 더 좁혀짐 — 조직 벽에 근접하는 신호가 이어짐. 비코드 불변 4건(SSO·실문서/부서·사내모델/cross-encoder·폐쇄망)이 진짜 병목.

## 2026-07-09 (4차) PM 오케스트라 종합 점검 — 3차 패널 8건 완료 후 재실행

CLAUDE.md 규칙 2-c에 따라 6직무 재실행.

### 🚨 신규 발견 — 보안 취약점 (PR #66의 후속 갭, 최우선)
`create_index_job`/`process_index_job`(PR #66에서 인가 추가)이 **읽기 권한 없는 자**의 포이즈닝은 막았지만, `force_reindex=true`에 동일한 read-ACL 바(`principal_can_access_document`)만 적용해 **읽기 권한은 있지만 신뢰할 수 없는 임의 principal**(기본 `access_groups=["all-employees"]`라 실질적으로 전 직원)이 여전히 **이미 색인된(신뢰 상태) 문서**의 벡터를 퍼지하고 조작된 텍스트로 재색인할 수 있음. PR #66이 막은 것은 "무권한자의 포이즈닝"이고 이번 발견은 "권한은 있으나 신뢰 못할 자의 포이즈닝" — 같은 취약점 계열의 축소된 후속판. 처음 색인(아직 신뢰할 콘텐츠 없음)엔 read-ACL 바가 적절하지만, 이미 색인된 문서의 `force_reindex`는 `PRIVILEGED_ROLES`/소유자 수준으로 상향 필요.

### PM 권고 (전 도메인 종합, 우선순위) — 4차
1. ✅ **`force_reindex` 재색인 인가 상향** (PR #83, opus, security-review 통과) — **구현 중 지시 오류를 스스로 발견·수정**: 원 지시는 "force_reindex=true일 때만" 게이팅하라 했으나, `run_index_job`의 벡터 퍼지(`store.delete_document`)가 **force_reindex 여부와 무관하게 성공 경로에서 항상 실행**됨을 코드 추적으로 확인 — force_reindex만 게이팅했으면 그냥 `source_text`만 보내는 동일한 공격이 여전히 뚫려 있었음. 대신 **`document.status == "indexed"`**(이미 신뢰콘텐츠 존재) 기준으로 `create_index_job`·`process_index_job` 둘 다에 `enforce_roles(PRIVILEGED_ROLES, action="document.reindex")` 추가(최초 색인은 read-ACL 그대로 유지, self-service 색인 흐름 무손상). security-review가 이 이탈의 근거를 코드로 직접 재확인(고신뢰), 우회경로 없음, admin 회귀 없음. 테스트 5종(첫색인 허용회귀없음·재색인거부+퍼지미발생증명(force_reindex 있/없음 둘 다)·admin우회). 함께 점검(미수정, 위험 아님으로 확인): `upload_document_and_index`는 항상 신규 문서 생성이라 기존 신뢰콘텐츠 타겟 불가. baseline 203.
2. ⛔→✅ **결정 완료(사용자, 2026-07-11): `create_source`/`register_document`/`upload_document_and_index`에 RBAC 추가 안 함** — 자기서비스형 지식 기여가 의도된 플랫폼 사용모델임을 확인, 현행 유지. 코드 변경 없음(정책 확인이 결론). 이 항목은 재논의 전까지 종결.
3. ✅ **CI에 `alembic upgrade head`(+downgrade/재upgrade)를 실 Postgres 서비스 컨테이너 대상으로 추가** (PR #85, sonnet) — `.github/workflows/ci.yml` backend job에 `postgres:16-alpine` service+healthcheck 추가, pytest 전에 마이그레이션 체인(0001→head→base→head) 실행. 로컬에서도 **별도 스크래치 컨테이너**(공유 세션 `compose-postgres-1`은 건드리지 않음)로 동일 시퀀스 실제 라이브 검증 후 삭제. **실 GitHub Actions 그린 확인**(머지 전 `gh pr checks`로 backend/frontend 둘 다 pass 재확인). pytest는 여전히 헌메틱(SQLite) 유지, 마이그레이션 체크만 분리된 별도 스텝.
4. ✅ **`/audit` 페이지를 데모 역할 스위처 패턴(PR #63)에 포함** (PR #86, sonnet) — 비admin은 fetch 자체를 스킵(403 왕복 없음)하고 Knowledge 페이지와 동일한 `role-restricted-note` 표시. **네비게이션 링크는 숨기지 않기로 결정**(의도적 설계 판단): 데모 역할 기능의 목적이 "역할별로 뭘 할 수 있는지 보여주는 것"이라 링크를 숨기는 것보다 제한 화면을 보여주는 게 RBAC 경계를 더 잘 시연함. e2e 4/4(신규)+전체 20/20 라이브 통과, tsc 클린. 백엔드 무변경(서버는 이미 정상 강제 중이었음).
5. ✅ **리랭커 `rerank_top_k` 컷오프 추가** (PR #89, fable) — 신규 `AGENT_FORGE_RERANK_TOP_K`(기본 None=무제한, 기존 동작 완전 동일). 컷오프 밖 히트도 `RetrievalHit` 행은 유지하되 `used_in_context=False`(감사/eval 가시성 보존 — eval의 top_score 계산이 리랭크로 밀린 히트를 놓치지 않도록). 테스트 12종, apps/api 215 passed. **라이브 실험 실제 수행**(`docs/eval-results-live-v0.5.md`): 패널 원안(min_score 0.35+hybrid+top_k2)은 **거부규율 88.9→22.2로 붕괴**(retrieval_min_score가 사실상 거부 게이트 겸임을 발견, 정직 보고) → `answer_min_score=0.53`으로 거부 게이트 분리 유지하니 거부규율 그대로+**useful_answer 83.3→91.7**(+8.4pt, 회귀 0, 2회 재현 안정). **이 조합(config C)을 실 배포 기본값으로 채택할지는 별도 결정 사항으로 남김**(코드에 반영 안 됨, `.env` 실험 후 원복). c07은 여전히 실패(스칼라로 못 잡는 시맨틱 케이스, 사내모델 대기 — 변함없음).
- **QA/PM 종합**: 이번 패스는 자연 감소 패턴과 다르게 **실제 보안 이슈 재발견**(패널의 "완결 선언 보류" 판단 근거). 나머지(hard-delete는 moot로 확인, self-commit 패턴은 안전, Alembic downgrade는 3번으로 승격)는 심각도 낮음. **"코드 완결" 선언 시기 아님.** **→ 4차 패널 5개 항목 전부 처리 완료**(1·3·4·5는 코드로 닫힘, 2는 사용자 결정으로 종결).

### 대기 중인 결정 사항 (사용자)
- **eval-results-live-v0.5의 config C**(`retrieval_min_score=0.35`+`rerank_backend=hybrid_lexical`+`rerank_top_k=2`+`answer_min_score=0.53`)를 실 `.env` 기본값으로 채택할지 — useful_answer +8.4pt 개선, 회귀 0, 2회 재현. 다만 로컬 qwen3:1.7b·소형 코퍼스(12케이스 중 1건 개선) 기준이라 사내모델(qwen3-30b-a3b) 이관 후 재검증 권장. **코드 변경 없음(순수 설정값 결정)** — 반영 시 `.env`만 교체.

## 2026-07-12 (5차) PM 오케스트라 종합 점검 — 4차 패널 5건 완료 후 재실행

CLAUDE.md 규칙 2-c에 따라 6직무 재실행(이번 패널은 Sonnet 5 실행, 이후 세션은 Fable 5로 전환됨).

### 🚨 신규 발견 — 보안 취약점 (PR #66·#83의 3번째 같은-계열 갭, 최우선)
PR #83의 재색인 인가 상향이 `document.status == "indexed"`만 기준으로 삼는데, `run_index_job`이 벡터 퍼지 **이후** 실패하면 문서가 `"index_failed"`로 떨어짐(VECTOR_UPSERT_FAILED 등). 그 상태에선 `create_index_job`/`process_index_job`이 `status=="indexed"`를 못 봐서 `PRIVILEGED_ROLES` 게이트가 조용히 미적용 → 비특권 co-reader가 임의 `source_text`로 재색인해 다시 `"indexed"`로 뒤집을 수 있음(원래 ACL/등급 태그 유지). PR #83이 닫은 co-reader 포이즈닝을 운영-실패 side door로 재개방. 테스트 부재 확인. **QA/PM 지적**: PR #66→#83→이번이 같은 근본 혼동("read-access ≠ 기존 신뢰콘텐츠 변경 권한")의 연속이라, 상태별 패치가 아니라 "이 문서가 신뢰 콘텐츠를 가진 적 있는가"를 추적하는 근본 수정이 맞음.

### PM 권고 (전 도메인 종합, 우선순위) — 5차
1. ✅ **재색인 인가를 "신뢰 콘텐츠 보유 이력" 기준으로 근본 수정** (PR #92, opus, security-review 통과) — 신규 durable 컬럼 `documents.has_been_indexed`(최초 성공 색인 시 True, **절대 리셋 안 됨** — archive/restore/index_failed 어디서도) + 마이그레이션 0005(server_default false + **기존 행 백필**: status="indexed" OR `document.indexed` 감사이벤트 보유 → True, 이미 신뢰콘텐츠 가진 문서 재노출 방지). 두 엔드포인트 게이트를 `status=="indexed"` → `has_been_indexed`로 변경. **에이전트가 실제 재현 가능 경로를 재특정**: 패널이 지목한 index_failed는 이미 `SEARCHABLE_DOCUMENT_STATUSES` 미포함이라 read-ACL tier에서 차단됨(defense-in-depth로 함께 닫음), 진짜 도달가능한 건 **archive→restore→registered**(searchable 상태) 경로 — durable 플래그가 이걸 닫음. security-review: 백필 이벤트명(`document.indexed`) 실제 emitter와 일치·플래그 리셋 경로 없음·최초색인/재시도 회귀 없음 모두 재확인, 발견 0건. 실 GitHub Actions CI(마이그레이션 0005 up/down/up 대상 Postgres 포함) 그린 확인 후 머지. 테스트 +5, baseline 220.
2. ✅ **`create_source`에 `default_confidentiality_level` 검증 추가** (PR #94, sonnet) — 형제 엔드포인트와 동일한 `_validate_confidentiality` 호출(db.add 전), 미인식 값은 422. 대소문자 무시·공백 미허용 모두 문서 엔드포인트와 일치. 테스트 4종(유효 4등급·mixed case·오타·공백). baseline 224.
3. ✅ **chat/agents-new의 ask 실패 에러렌더 수정** (PR #95, sonnet) — `setAnswer(String(e))` → 별도 `askError` 상태로 분리(실패 시 answer/citations 비우고 빨간 `ask-error` 요소로 표시, 답변카드 오염 안 됨). 부수: runs 페이지 로딩상태(false empty-state flash 제거)·chat textarea aria-label. e2e는 **route 목킹**으로 라이브 스택 없이 실패경로 검증(2 passed, Docker 데몬 다운 상태라 나머지 전체 라이브 스위트는 미실행·정직 명시). tsc 클린.
4. ✅ **e2e를 CI에서 실행** (PR #97, fable) — **패널이 제안한 fake LLM 스텁이 불필요함을 확인**(최소 충실 구성 우선 탐색): `AGENT_FORGE_LLM_BASE_URL` 미설정 시 결정적 fallback 답변 + `FakeVectorStore` 기본값이라 **Qdrant·Ollama·fake-LLM 전부 없이** Postgres 서비스 컨테이너만으로 실제 파이프라인(색인·ACL·검색) 구동. 모든 e2e 스펙이 LLM 답변 문구가 아닌 구조/RBAC를 검증함을 코드로 확인(chat.spec는 route 목킹). CI e2e job: Postgres 컨테이너 + alembic + seed_demo/seed_demo_rich + 라이브 run 1개 시드 + 프로덕션 standalone 빌드(Dockerfile.prod 미러) + Playwright. **실 GitHub Actions 첫 런에 green**(21/21, push-observe-fix 반복 불필요). 기존 backend/frontend job 무변경. `--retries=1`+실패 시 trace/log 아티팩트 업로드. **→ 5차 패널 4개 항목 전부 완료.**

### 코드-now 백로그 소진 상태 (2026-07-14)
5차 패널 4건 완료 후, 현재까지 도출된 모든 코드-now 항목이 닫힘. QA/PM 5차 판정은 "코드 완결 문턱 도달, 5회 연속 매번 뭔가 나온 뒤라 한 번 더 확인 패스 후 정식 선언 권고".

### 6차 확인 패널 — **자원 한도로 미완(부분 결과)** (2026-07-14)
CLAUDE.md 2-c 정식 트리거를 위한 6차 확인 패널을 실행했으나 **하드 세션 사용량 한도**에 걸려 6직무 중 5개(보안·RAG·백엔드·프론트·QA/PM) 실행 실패(한도 리셋: 06:00 KST). **DevOps 1개만 완주** — "DevOps 코드-now 소진, EP-07(폐쇄망) 결정 대기, 정식 코드완결 선언 찬성" 결론(Dockerfile.prod 배선·JSON로깅 미들웨어 둘 다 EP-07 전까지 shelfware로 재확인, bitrot은 PR #97 e2e가 standalone 번들을 매 PR 빌드·구동해 이미 커버).

**잠정 판정(정식 아님)**: 5개 완주 패널이 도출한 모든 코드-now 항목이 닫히고 검증됨(보안 3건 리뷰통과, e2e 실CI green). 6차 확인 패널 1/6만 완주했고 그것도 소진 확인 → 코드-now 백로그는 **실질 소진**으로 보이나, 2-c 문언("패널이 더는 못 냄")의 정식 트리거는 확인 패널이 **깨끗이 무-산출로 완주**하는 것이므로 아직 **정식 "코드 완결" 선언 보류**. 자원 리셋(06:00 KST) 후 6차 확인 패널 재실행 → 무-산출이면 그때 정식 선언.

**다음 작업(자원 리셋 후)**: 6차 확인 패널 재실행(6직무, Fable). 무-산출 시 CLAUDE.md 2-c에 따라 **"코드 완결"(남은 건 전부 비코드 의존) 정식 선언**. 비코드 불변: SSO IdP · qwen3-30b-a3b/cross-encoder 실측 · 실문서/파일럿 부서 · 폐쇄망 EP-07 · config-C 채택 결정.
- **QA/PM 종합**: 백로그 매우 얇음. QA/PM 자체 스윕은 새 코드-now 못 냄(패널 시리즈 최초) — "코드 완결" 문턱 도달. 다만 5회 연속 매번 뭔가 나온 뒤 첫 클린 패스라, 한 번 더 확인 패스 후 정식 선언 권고. 비코드 불변 4건(SSO·사내모델·실문서·폐쇄망) + config-C 채택 결정만 남음.

## 2026-07-16 — UI 디자인 시스템 슬라이스 (사용자 제기, 패널 외 코드-now)
사용자가 "가독성/가시성/UI 이쁨"을 제기 → 이는 기능/보안 패널이 안 건드린 실재 코드-now 항목이라 **잠정 코드완결을 취소**하고 슬라이스로 진행. brainstorming→spec(`docs/superpowers/specs/2026-07-14-web-design-system-design.md`)→구현.
- ✅ **경량 디자인 시스템** (PR #103) — globals.css 디자인 토큰(시맨틱 색·**라이트+다크** prefers-color-scheme+`[data-theme]`·간격/타이포/radius/shadow), 컴포넌트 클래스(button/badge/field/table/nav) 정제로 인라인 하드코딩 치환, 신규 `ThemeSwitcher`(light/dark/system, localStorage)+`NavLinks`, **Pretendard self-host**, 전 페이지 리스타일. 백엔드 무변경, Tailwind/JS컴포넌트lib 미도입.
- **진행 특이사항**: Fable 프론트 서브에이전트가 세션 한도로 결과 null 반환했으나 **작업 트리에 전체 구현을 남김** → 오케스트레이터가 브랜치로 보존 후 **직접 검증·마무리**(서브에이전트 재디스패치가 한도로 막힘). 검증: tsc 클린·`npm run build` 클린(12페이지·Pretendard OK)·**기존 data-testid 51개 전부 보존(0 유실, +theme-switcher)** testid 셋 diff로 확인·route-mock chat 스펙 2/2·**실 CI 21개 e2e 그린(2m3s, 최종 게이트)**. 회귀 0 입증 후 머지.
- **의미**: 이 사용자 제기 항목이 닫히면서 코드-now 백로그 재소진. 정식 "코드 완결"은 여전히 6차 확인 패널 클린 완주 대기(위 참조).

## Go/No-Go 권고
- **기술 MVP: GO 가능** — 핵심 가치(권한 기반 인용 답변 + 누출 0)가 코드·eval로 성립.
- **파일럿 진입: 조건부 HOLD** — 코드 문제 아님. 위 "결정 → 해제 표"의 4개 입력(파일럿 부서/실문서·SSO·사내모델·폐쇄망)이 채워져야 진입 가능.
- **권고 순서**: (조직) 파일럿 부서·실문서 + SSO 결정 착수 ∥ (코드, 내가 가능) 위 "PM 권고" 1→6 순서, **1번(CI)부터 단일 슬라이스로**.
