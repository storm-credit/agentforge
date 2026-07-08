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
1. **(다음 슬라이스, 최우선, 단일 슬라이스로) CI 워크플로** — pytest+ruff+tsc on PR. QA/PM 강력 권고 채택: 이번 venv 사고의 재발 방지 안전망을 다음 병렬 배치 전에 깔아야 함. S.
2. 문서 unarchive(복원) API — PR#49가 노출시킨 비대칭 해소. S.
3. `POST /agents/versions` RBAC + `GET /knowledge/sources` confidentiality_rank 부분 필터 — 검증된 패턴 재적용. 둘 다 S.
4. `readyz`에 Qdrant/객체스토어 체크 추가. S.
5. `grounding_score` → eval faithfulness_pct 게이트 배선. S, 결정적.
6. (여력 시) 역할별 UI(RBAC 시연) — 이제 언블록, 데모 완성도용. M.
- **c07 스레드**: 공식 종결 — 추가 스칼라 땜질 금지, 사내모델/실 리랭커 대기로 문서화.
- **비코드 불변**: SSO IdP, qwen3-30b-a3b/cross-encoder 실측, 실문서/파일럿 부서, 폐쇄망 EP-07 — 조직 결정 필요.

## Go/No-Go 권고
- **기술 MVP: GO 가능** — 핵심 가치(권한 기반 인용 답변 + 누출 0)가 코드·eval로 성립.
- **파일럿 진입: 조건부 HOLD** — 코드 문제 아님. 위 "결정 → 해제 표"의 4개 입력(파일럿 부서/실문서·SSO·사내모델·폐쇄망)이 채워져야 진입 가능.
- **권고 순서**: (조직) 파일럿 부서·실문서 + SSO 결정 착수 ∥ (코드, 내가 가능) 위 "PM 권고" 1→6 순서, **1번(CI)부터 단일 슬라이스로**.
