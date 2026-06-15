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
| **rerank / query rewrite / LLM-judge** | ⛔ | 사내 cross-encoder/35B 필요(Ollama rerank 미지원 확인) — **거부 규율 약점(refusal_discipline 66.7%)의 정공법** |
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
| E2E 테스트 | ✅(코드) | Playwright 12 + 백엔드 102 passed |
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
| 사내 모델(Qwen3.6:35B) + cross-encoder 가용 | 인프라/AI | rerank·LLM-judge·query rewrite → **거부 규율 66.7%→개선**, useful 재측정. 옵션·추천: [research-reranking-options.md](research-reranking-options.md) |
| 폐쇄망 staging 환경(EP-07) | DevOps | 실배포·운영 전환 |

## 내가 결정 없이 코드로 닫을 수 있는 것 (🔧)
1. ✅ **버전 자동증가 + "새 버전 생성" UI** (PR #28).
2. ✅ **run 조회 인가(owner/admin 스코프)** (PR #29). (문서목록 메타 스코프는 빌더 영향+정책 미정으로 의도적 보류.)
3. ✅ **MinIO 객체저장소 배선 + 객체스토어 fetch 인제스트(AF-009)** (PR #30). opt-in(기본 none), 실 MinIO 라이브 검증. ([object-storage-af009.md](object-storage-af009.md))
4. ✅ **rerank 인터페이스/스텁** (PR #31) — runs.py rerank 훅(noop 기본, env 게이트), 실제 cross-encoder는 사내 모델 가용 시 연결. ([research-reranking-options.md](research-reranking-options.md))

5. ✅ **롤백 / 버전 config 디프 뷰** (PR #32) — WS4 버전 라이프사이클 완성.
6. ✅ **LLM-as-judge 답변가능성 게이트** (PR #33) — 코드 훅(local Ollama로 동작, env `AGENT_FORGE_JUDGE_BACKEND`, 기본 off). **측정 결과: 로컬 qwen3:1.7b론 거부규율 개선 없음(citation 100→91.7 하락)** → 실질 개선은 사내 35B 대기. 훅은 이식 레버로 유지. ([eval-results-judge-v0.4.md](eval-results-judge-v0.4.md))

### 보안/거버넌스 군집 (전문가 패널 도출, 코드-now)
7. ✅ **mutation 엔드포인트 RBAC** (PR #35) — `enforce_roles`/`PRIVILEGED_ROLES`로 ACL 변경·게시·검증을 admin/platform-admin/knowledge-manager로 제한, 거부 시 `policy.denied` 감사. + 문서 create/upload `confidentiality_level` 검증 추가. 라이브: developer 403 / admin 200.
   - 군집 잔여(🔧): 감사 조회 API(WS2/4) · 문서 ACL 편집 UI(WS7) · 문서 소프트삭제+Qdrant 퍼지(WS4) · 문서목록/청크 GET ACL 스코프(WS2).
   - 보류(정책): 문서 *생성/업로드* 시 등급 지정의 역할 게이팅(operator-vs-end-user 정책 필요 — SSO기). PATCH(기존 문서 재분류)는 게이팅됨.

### 아직 코드로 닫을 수 있으나 미착수 (🔧 남음 — "완결" 아님)
- 위 보안/거버넌스 군집 잔여 4건(감사 조회 API · ACL 편집 UI · 문서 삭제 · 목록 스코프).
- 측정/무결성(QA): 지연·trace 스코어러 · 코퍼스 v0.3(suite·n↑) · rerank score_rerank 배선.
- 배포(DevOps): 프로덕션 Dockerfile/compose · 게이트웨이 인증 토큰 · `.env.example` 완성.
- **프롬프트 인젝션 하드닝 보강**(WS2) — 천장 낮음(모델 의존), 후순위.
- (문서목록 GET 메타 스코프 — 위 군집에 포함.)

> **거부규율(c07) 갱신:** scalar 게이트(v0.3)·로컬 1.7b judge(v0.4) 모두 못 고침. 코드 토대(judge 훅 + rerank 훅)는 깔렸고, 실질 개선은 사내 35B/cross-encoder 대기(⛔ 모델). rerank는 Ollama 미지원으로 로컬 검증 불가.

## Go/No-Go 권고
- **기술 MVP: GO 가능** — 핵심 가치(권한 기반 인용 답변 + 누출 0)가 코드·eval로 성립.
- **파일럿 진입: 조건부 HOLD** — 코드 문제 아님. 위 "결정 → 해제 표"의 4개 입력(파일럿 부서/실문서·SSO·사내모델·폐쇄망)이 채워져야 진입 가능.
- **권고 순서**: (조직) 파일럿 부서·실문서 + SSO 결정 착수 ∥ (코드, 내가 가능) 버전 자동증가 → GET 인가로 데모/배포 신뢰도 보강.
