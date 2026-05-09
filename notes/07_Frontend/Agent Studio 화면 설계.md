# Agent Studio 화면 설계

## 1. 제품 관점

Agent Studio MVP는 폐쇄망 내부 관리자가 문서 기반 RAG 에이전트를 만들고, 테스트하고, 배포 전 품질을 확인하는 작업 콘솔이다. 첫 화면은 마케팅형 랜딩이 아니라 agent 운영 목록이어야 한다.

주 사용자:

- 현업 Agent Owner: 문서 소스 선택, 프롬프트/응답 정책 설정, 테스트 질문 실행
- 운영 관리자: 모델/기본 정책/배포 승인/로그 확인
- QA 담당자: 평가셋 실행, 회귀 결과 확인
- 일반 사용자: published agent에 질문하고 citation이 있는 답변을 확인

## 2. 기술 기준

- Framework: Next.js App Router
- UI 구성: 서버 컴포넌트는 목록/상세 조회에 사용하고, Builder/Test Chat/Trace는 클라이언트 컴포넌트로 구성한다.
- 상태 관리: TanStack Query로 API cache와 mutation 상태를 관리한다. Builder 내부 form state는 React Hook Form + Zod를 권장한다.
- 인증: 사내 SSO 연동 전까지 dev mock principal 선택기를 제공하되, 운영 빌드에서는 제거한다.
- 접근성: 모든 주요 액션 버튼은 keyboard focus, aria-label, loading/disabled 상태를 제공한다.
- 화면 밀도: 운영 콘솔 성격이므로 정보 스캔이 쉬운 table, split pane, tab, drawer를 우선한다.

## 3. IA / Route 초안

| Route | 화면 | 목적 | 핵심 API |
|---|---|---|---|
| `/agents` | Agent 목록 | 생성/검색/상태 확인 | `GET /agents` |
| `/agents/new` | Agent Builder 신규 | 신규 agent와 draft version 생성 | `POST /agents`, `POST /agents/{id}/versions` |
| `/agents/[agentId]` | Agent 상세 | 배포 상태, 버전, 최근 실행 요약 | `GET /agents/{id}`, `GET /runs` |
| `/agents/[agentId]/builder/[versionId]` | Agent Builder 편집 | draft version 편집/검증/배포 요청 | version APIs |
| `/agents/[agentId]/test` | Test Chat | published 또는 draft version 테스트 | `POST /runs`, `GET /runs/{id}/events` |
| `/runs/[runId]` | Run Trace Viewer | 실행 단계, 검색 근거, guardrail 확인 | run APIs |
| `/knowledge` | Knowledge Source 목록 | 소스/문서/인덱싱 상태 확인 | knowledge APIs |
| `/knowledge/[sourceId]` | Source 상세 | 문서 업로드, ACL, 인덱싱 job | document APIs |
| `/eval` | Eval Dashboard | 평가 suite 실행/결과 비교 | eval APIs |
| `/admin/settings` | Admin Settings | 모델, 기본 정책, 보존기간 | settings APIs |
| `/audit` | Audit Explorer | 감사 이벤트 검색 | audit APIs |

## 4. 글로벌 레이아웃

좌측 내비게이션:

- Agents
- Knowledge
- Evaluations
- Runs
- Audit
- Admin

상단 바:

- 현재 principal/부서 표시
- 환경 배지: `DEV`, `STAGING`, `CLOSED-NET PROD`
- 검색
- 알림: 인덱싱 실패, 평가 실패, 승인 대기

공통 컴포넌트:

- `StatusBadge`: draft/published/indexed/failed 등 상태 색상
- `PolicyBadge`: citation required, PII masking, restricted docs 등
- `CitationLink`: 문서명, page, chunk id, score 표시
- `RunStepTimeline`: 단계별 latency/status
- `EmptyState`: 다음 액션 버튼을 포함하되 장식적 설명은 최소화
- `ErrorPanel`: problem response의 code/detail/request_id 표시

## 5. Agent 목록

목적: 사용자가 운영 중인 agent를 빠르게 찾고 상태를 판단한다.

주요 UI:

- 상단 액션: `New Agent`
- 필터: 상태, 소유 부서, 태그, knowledge source, 최근 실행 실패 여부
- 테이블 컬럼: 이름, 상태, published version, 소유 부서, 지식 소스 수, 최근 실행 수, 실패율, 마지막 배포일
- row 클릭: Agent 상세
- row 액션: 테스트, Builder 열기, Archive

상태 처리:

- `draft`: Builder로 유도
- `published`: Test Chat 바로 열기
- `archived`: 기본 목록에서 숨김, 필터로 표시
- 최근 run 실패율이 임계치 초과하면 warning badge 표시

## 6. Agent 상세

탭 구성:

- Overview: 목적, owner, published version, 최근 지표
- Versions: draft/validated/published/superseded 목록과 diff
- Knowledge: 연결된 source, 문서 수, indexing 상태
- Runs: 최근 실행 로그
- Evaluations: 최근 평가 결과
- Settings: archive, visibility, owner 변경

주요 지표:

- 최근 24시간 실행 수
- 성공률/정책 거부율
- 평균 latency
- citation 포함률
- no answer 비율
- top 실패 코드

## 7. Agent Builder

Builder는 wizard형 흐름을 기본으로 하되, 좌측 stepper와 우측 live validation panel을 둔다. 사용자는 중간 저장을 자주 해야 하므로 모든 단계는 draft autosave를 지원한다.

### Step 1. 기본 정보

입력:

- 이름
- 목적 설명
- 소유 부서
- visibility: private/department/organization
- 태그

검증:

- 이름 중복
- 목적 설명 최소 길이
- 소유 부서가 principal 권한 범위인지 확인

### Step 2. 모델 선택

입력:

- Chat model: `local-llm-8b`, `local-llm-14b`, 사내 gateway 등록 모델
- Temperature slider: 기본 0.2
- Max tokens
- Timeout

표시:

- 모델 상태: available/degraded/offline
- context window
- GPU serving endpoint
- 보안 승인 등급

### Step 3. 지식 소스 선택

입력:

- Knowledge source multi-select
- 문서 등급 허용 범위
- 검색 top_k, rerank_top_k
- min score
- citation required toggle

보조 패널:

- 선택한 source별 indexed 문서 수
- restricted/confidential 문서 수
- 최근 인덱싱 실패
- 권한상 사용할 수 없는 source는 disabled + reason 표시

### Step 4. 정책/가드레일

입력:

- citation 없으면 답변 거부
- 근거 부족 시 fallback 문구
- PII masking
- prompt injection 경고 대응 방식
- 답변 언어: 기본 한국어
- 금지 주제/민감 키워드

검증:

- restricted 문서를 선택했는데 ACL 정책이 비어 있으면 publish 차단
- citation required off는 admin 승인 필요
- confidential 등급 문서는 MVP 기본 exclude

### Step 5. 응답 스타일

입력:

- 답변 톤: concise/business/helpdesk
- citation 표시 형식: inline/endnote/both
- 모르는 경우 응답 문구
- 표/절차형 응답 선호 여부

Preview:

- 예시 질문에 대한 skeleton answer 표시
- citation placeholder 표시

### Step 6. Test & Validate

구성:

- 좌측: 테스트 질문 목록, 직접 질문 입력
- 중앙: 답변과 citation
- 우측: retrieval hits, guardrail result, latency/token usage

액션:

- `Run Test`
- `Retrieval Preview`
- `Save as Eval Case`
- `Validate for Publish`

배포 전 필수 통과:

- schema validation 성공
- 최소 5개 smoke test 실행
- citation required agent는 citation 포함률 100% in smoke test
- ACL denial smoke test 1개 이상 통과

### Step 7. Publish

표시:

- version diff
- 연결 source와 문서 count
- 평가 요약
- known risks
- 승인자/승인 상태

MVP 버튼:

- `Publish`는 admin 권한에서 즉시 가능
- 일반 agent_owner는 `Request Publish`로 approval row 생성

## 8. Knowledge Source 화면

### 목록

컬럼:

- 이름
- 타입
- 소유 부서
- 문서 수
- indexed/failed/revoked count
- 기본 등급
- 마지막 sync/index 시각

필터:

- source type
- status
- owner department
- failed jobs only

### Source 상세

탭:

- Documents
- ACL
- Index Jobs
- Settings

Documents 탭:

- 파일 업로드 dropzone
- 문서 테이블: 제목, 등급, ACL 요약, status, chunk 수, 마지막 index
- row 액션: 상세, 재인덱싱, 검색 제외, ACL 수정

ACL 탭:

- 기본 ACL 편집
- 부서/역할/user별 read/admin 권한
- explicit deny 표시
- 변경 시 audit event preview

Index Jobs 탭:

- stage별 진행률: parse/chunk/embed/upsert
- 실패 문서 재시도
- error code와 request id 표시

## 9. Test Chat

목적: 실제 사용자가 보는 답변 경험과 운영자가 보는 디버그 정보를 한 화면에서 분리한다.

레이아웃:

- 좌측: 대화 목록 또는 테스트 질문 preset
- 중앙: 채팅 transcript
- 우측 drawer: citation, retrieval, run step debug

채팅 메시지:

- 답변 아래 citation chip 표시
- citation 클릭 시 source preview drawer 열림
- 근거 부족 답변은 일반 답변과 다른 neutral 상태 badge 표시
- 정책 거부는 이유 code와 요청 가능 액션 표시

Draft 테스트:

- published version이 아닌 draft version 테스트 시 상단에 `Draft Test` badge
- 결과는 운영 사용자 통계에서 제외하되 run/eval 로그에는 남긴다.

## 10. Run Trace Viewer

상단 요약:

- run id, agent/version, user/department, status, latency, created_at
- request id, trace id
- 정책 결과

본문 탭:

- Timeline: guard_input, planner, retriever, reranker, generator, guard_output
- Retrieval: vector 후보, rerank 결과, ACL filter snapshot
- Answer: 최종 답변, citation mapping, no-answer reason
- Logs: error code, stack trace는 admin만
- Feedback: 사용자 피드백, QA review

Retrieval 테이블 컬럼:

- rank original/reranked
- score vector/rerank
- document title
- page/section
- confidentiality level
- ACL matched principal
- used in context
- used as citation

보안:

- 운영자가 권한 없는 문서 내용 preview를 열 수 없도록 문서 ACL을 다시 확인한다.
- QA/admin이라도 confidential 문서는 별도 권한이 없으면 metadata만 표시한다.

## 11. Eval Dashboard

기능:

- suite별 case 수와 최근 pass rate
- agent version 선택 후 평가 실행
- baseline과 diff 비교
- 실패 case drill-down

표시 지표:

- faithfulness
- answer relevance
- citation coverage
- ACL violation count
- refusal correctness
- latency p50/p95

액션:

- `Run Suite`
- `Approve Baseline`
- `Export Report`
- `Create Issue` 또는 추후 PM 도구 연결

## 12. Admin Settings

섹션:

- Models: chat/embedding/reranker gateway 등록 상태
- Retrieval Defaults: top_k, rerank_top_k, min_score
- Security Defaults: citation required, PII masking, retention days
- Offline Package: 현재 배포 이미지/모델/패키지 버전
- Maintenance: index rebuild, vector snapshot, backup status

운영 위험 버튼은 확인 modal과 audit reason 입력을 요구한다.

## 13. 프론트엔드 작업 분해

1. App shell, navigation, principal provider, API client 생성
2. Agent 목록/상세 읽기 화면
3. Builder form schema, draft 저장, validation panel
4. Knowledge source/document upload와 index job polling
5. Test Chat과 SSE event 처리
6. Run Trace Viewer
7. Eval Dashboard
8. Admin/Audit 화면
9. Playwright smoke test와 접근성 체크

## 14. 주요 E2E 시나리오

1. Admin이 knowledge source를 만들고 PDF를 업로드한 뒤 인덱싱 완료를 확인한다.
2. Agent Owner가 source를 선택해 draft agent를 만들고 테스트 질문을 실행한다.
3. citation이 없는 답변이 발생하면 Builder validation panel에서 실패 이유를 확인한다.
4. ACL이 없는 사용자의 질문이 정책 거부 또는 no-context로 처리되는지 확인한다.
5. Admin이 버전을 publish하고 일반 사용자가 Test Chat에서 답변을 받는다.
6. QA가 eval suite를 실행하고 실패 case를 Run Trace로 drill-down한다.
