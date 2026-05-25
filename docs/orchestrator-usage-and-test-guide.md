# Orchestrator Usage and Test Guide

이 문서는 Agent Forge를 처음 보는 사람이 "오케스트라가 뭔지", "지금 뭘 쓸 수 있는지", "잘 만들어졌는지 어떻게 테스트하는지"를 바로 확인하기 위한 운영자용 안내서다.

## 1. 오케스트라가 하는 일

오케스트라는 앱 안의 버튼 하나라기보다, 프로젝트와 런타임을 통제하는 총괄 방식이다.

| 질문 | 답 |
|---|---|
| 무엇을 관리하나 | 범위, 우선순위, 전문가별 산출물, 보안/평가 gate, 테스트 증거 |
| 왜 필요한가 | RAG, ACL, citation, 모델 품질, 감사 로그가 따로 놀지 않게 묶기 위해 |
| 지금 어디에 있나 | `notes/00_Orchestrator`, `docs/`, backlog, eval runner, smoke scripts |
| 사용자는 뭘 보면 되나 | Agent Studio UI, Eval report, Trace/Audit, smoke test 결과 |

핵심은 간단하다.

1. 문서를 올린다.
2. 인덱싱한다.
3. 권한에 맞는 문서만 검색되는지 본다.
4. 답변에 citation이 붙는지 본다.
5. trace/audit로 재현 가능한지 본다.
6. local model과 company model lane으로 품질을 검증한다.

## 2. 현재 만들어진 것

현재 Sprint 1 기준으로 확인된 기능:

- Agent CRUD와 version publish
- Knowledge source 생성
- Markdown/TXT 문서 업로드
- object storage 저장, checksum, MIME 기록
- index job과 chunk 생성
- ACL 필터가 적용된 retrieval preview
- runtime run 생성
- citation validator
- run steps, retrieval hits, audit events 저장
- Eval report 저장
- Agent Studio 주요 화면과 Trace Viewer
- Agent Studio Test Chat draft
- local deterministic model gateway provenance
- optional OpenAI-compatible local model gateway for authorized runtime answers
- Agent Studio API-backed agent catalog sync and versioned Test Chat runs
- Agent Studio draft creation, v1 version creation, validate, and publish workflow
- Agent Studio Knowledge API source picker for binding draft versions to real sources
- 로컬 Docker Qwen3 8B `local-regression` lane
- 회사 Qwen3.6 35B/vLLM `company-quality` lane 연결 준비

아직 남은 것:

- 회사 vLLM 실제 endpoint로 Golden Test 실행
- 한국어 업무 톤과 추천 이유 human review 연결
- 실제 파일럿 부서/문서/권한 확정
- 운영용 SSO/권한 원천 연동

## 3. 가장 빠른 사용법

PowerShell에서 repo root로 이동한다.

```powershell
cd "C:\Users\Storm Credit\Documents\New project"
```

로컬 Qwen3가 꺼져 있으면 켠다.

```powershell
docker start wset-ollama
```

전체 smoke와 local-regression eval을 한 번에 실행한다.

```powershell
./tools/smoke/api-eval-runner-smoke.ps1 `
  -BootStack `
  -WebPort 0 `
  -KeepStack `
  -ValidationLane local-regression `
  -ModelBaseUrl "http://127.0.0.1:11434/v1" `
  -ModelId "qwen3:8b" `
  -ModelProvider local-ollama `
  -ModelEndpointAlias docker-wset-ollama `
  -ModelTimeoutSeconds 120 `
  -TraceLatencyThresholdMs 5000
```

성공하면 다음이 통과해야 한다.

- compose boot
- synthetic corpus 30 cases
- scorer unit tests
- real upload-to-runtime smoke
- API-backed eval 30 cases
- local Qwen3 model probe
- local trace/latency gate

`-KeepStack`을 붙였으면 Web URL과 API URL이 살아 있다. 출력에 나온 Web URL을 열고 `Knowledge`, `Eval`, `Audit`, `Trace` 화면을 확인한다.

로컬 runtime answer generator도 Docker Ollama/OpenAI-compatible endpoint로 직접 붙이고 싶으면 API 실행 환경에 아래 값을 준다. 기본값은 여전히 deterministic fake라서 일반 회귀 테스트는 깨지지 않는다.

```powershell
$env:AGENT_FORGE_MODEL_GATEWAY_MODE="openai-compatible"
$env:AGENT_FORGE_MODEL_GATEWAY_OPENAI_BASE_URL="http://127.0.0.1:11434/v1"
$env:AGENT_FORGE_MODEL_GATEWAY_MODEL_ID="qwen3:8b"
$env:AGENT_FORGE_MODEL_GATEWAY_PROVIDER="local-ollama"
$env:AGENT_FORGE_MODEL_GATEWAY_ENDPOINT_ALIAS="docker-wset-ollama"
$env:AGENT_FORGE_MODEL_GATEWAY_TIMEOUT_SECONDS="120"
```

## 4. 화면에서 확인할 것

Agent Studio에서 보는 순서:

1. `Agents`: Knowledge API source를 선택해 draft agent와 v1 version을 만들고, validate/publish gate를 통과시킨 뒤 `Sync API`로 published/validated agent version을 불러온다.
2. `Knowledge`: 문서 업로드, 인덱싱, retrieval preview가 되는지 확인
3. `Eval`: 최근 eval run이 저장되어 있는지 확인
4. `Trace`: run ID로 단계별 실행 흐름을 확인
5. `Audit`: 문서 업로드, 인덱싱, retrieval, run 이벤트가 남는지 확인

좋은 상태:

- Published version에서만 Test Chat이 열리고, `agent_version_id`, `knowledge_source_ids`, citation, guardrail status, Trace link를 보여준다.
- Validated version은 Test Chat 전 단계이며, publish gate를 먼저 통과해야 한다.
- 선택한 Knowledge source와 수동 fallback ID가 중복 제거된 `knowledge_source_ids`로 version config와 runtime payload에 이어진다.
- 업로드한 문서 ID가 retrieval hit와 citation까지 이어진다.
- 권한 없는 문서는 retrieval result에 나오지 않는다.
- 답변이 citation 없이 성공 처리되지 않는다.
- trace step이 `guard_input -> retriever -> generator -> citation_validator -> guard_output` 순서로 남는다.
- audit event가 source, upload, index, preview, publish, run까지 이어진다.

## 5. 테스트 종류

| 테스트 | 명령 | 의미 |
|---|---|---|
| API unit/contract | `cd apps/api; uv run pytest` | API 계약, ACL, runtime, eval 저장 검증 |
| Eval harness unit | `python -m unittest discover eval/harness/tests` | scorer와 model probe 로직 검증 |
| Web E2E | `cd apps/web; npm run test:e2e` | Agent Studio 화면 흐름 검증 |
| Real ingestion smoke | `./tools/smoke/real-ingestion-smoke.ps1 -ApiBaseUrl "http://127.0.0.1:8000/api/v1"` | 실제 업로드부터 runtime citation까지 검증 |
| Full local regression | `./tools/smoke/api-eval-runner-smoke.ps1 -BootStack -WebPort 0 -ModelTimeoutSeconds 120 -TraceLatencyThresholdMs 5000 ...` | 로컬 스택, 실제 업로드, 30-case eval, 모델 probe, trace gate를 한 번에 검증 |
| Company quality | `./tools/smoke/api-eval-runner-smoke.ps1 -ValidationLane company-quality ...` | 회사 vLLM 품질 gate 검증 |

## 6. 로컬 LLM과 회사 vLLM 차이

| Lane | 모델 | 용도 | 합격의 의미 |
|---|---|---|---|
| `local-regression` | Docker `wset-ollama`의 `qwen3:8b` | 연동, ACL, citation, trace, timeout 회귀 확인 | 배관과 안전장치가 안 깨졌다 |
| `company-quality` | 회사 Qwen3.6 35B/vLLM | 최종 답변 품질, 한국어 업무 톤, 추천 이유 설득력 | 운영 품질 후보가 될 수 있다 |

로컬 8B가 통과해도 최종 품질 승인은 아니다. 회사 35B/vLLM과 human review까지 통과해야 release candidate로 본다.

전문가별 모델 선택:

| 전문가 | 루틴/초안 | 승격/릴리스 |
|---|---|---|
| 오케스트라, PM, 아키텍처, AI Runtime, RAG, Backend, Frontend, DevOps, QA/Eval | `local-qwen8b` | `company-qwen35b` |
| 보안 아키텍트 | `company-qwen35b` | `company-qwen35b` |

보안은 처음부터 deep-review다. 다른 전문가는 로컬 8B로 초안/회귀를 빠르게 돌리고, 릴리스 판단이나 정책 충돌이 생기면 회사 35B/vLLM 증거가 필요하다.

## 7. 현재 확인된 최신 증거

최근 local-regression 실행 결과:

- Docker model: `wset-ollama`
- model endpoint: `http://127.0.0.1:11434/v1`
- model id: `qwen3:8b`
- model probe: succeeded with `-ModelTimeoutSeconds 120`
- API-backed eval: 30/30 passed
- real upload-to-runtime smoke: passed
- trace gate: run ID, ordered steps, retrieval hits, p50/p95 latency summary required

주의할 점:

- Qwen3는 health probe에서 `<think>` 텍스트를 낼 수 있다. 그래서 eval report의 `summary.quality_review`에는 final answer cleanliness gate가 들어간다. 최종 답변에는 `<think>`/`</think>`가 나오면 blocker다.
- `company-quality` lane은 `answer_naturalness`, `korean_business_tone`, `recommendation_rationale`, `groundedness`를 1~5점으로 보고, 각 항목 4점 이상과 human review가 필요하다.
- 회사 vLLM endpoint는 아직 실제 값이 필요하다.

## 8. 잘 만들어졌는지 판단하는 기준

잘 만들어졌다고 보려면 문서가 아니라 증거가 있어야 한다.

| 영역 | 최소 합격 기준 |
|---|---|
| Backend | contract tests 통과 |
| RAG | 업로드 문서가 chunk, retrieval hit, citation으로 이어짐 |
| Security | ACL 위반 0건 |
| Runtime | run steps와 retrieval hits가 저장됨 |
| QA/Eval | synthetic 30 cases 통과 |
| Frontend | Playwright smoke 통과 |
| Model | local-regression probe 성공, company-quality probe 성공 |
| Audit | 주요 이벤트가 재현 가능하게 저장됨 |

오케스트라의 역할은 이 기준을 하나씩 체크하고, 부족한 영역을 다음 작업으로 다시 배정하는 것이다.
