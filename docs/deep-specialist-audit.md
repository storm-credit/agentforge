# Deep Specialist Audit

Date: 2026-05-14

Orchestrator conclusion: the specialist structure is real, but the project must distinguish design depth from implementation verification.

Most specialist workstreams are now at D2 for design. That means they include domain rules, risks, constraints, acceptance criteria, and cross-workstream dependencies. D3 is not broadly complete yet. D3 requires executable checks: contract tests, integration tests, policy tests, UI E2E, offline install smoke tests, and evaluation reports.

## 1. Verdict

| Question | Answer |
|---|---|
| Is the orchestrator actually governing the work? | Yes. Scope, gates, dispatch board, ADRs, official docs, backlog, and Sprint 0 skeleton are connected. |
| Are the specialists deep? | Mostly yes at D2 design depth. RAG, Security, AI Runtime, DevOps, QA, Frontend, Backend, and Architecture have domain-specific rules and gates. |
| Are they D3 verifying specialists yet? | Not yet overall. Backend has a Sprint 0 skeleton and minimal tests, but most D3 verification remains pending. |
| Is the product runtime multi-agent yet? | No. Current multi-agent behavior is project orchestration. Product runtime agents will come through later Agent Registry, Runtime, eval, and audit features. |

## 2. Depth Scorecard

| Specialist | Current Depth | Evidence | Gap To D3 | Orchestrator Decision |
|---|---:|---|---|---|
| Orchestrator | D2.7 | Operating model, dispatch board, ADRs, docs index, model routing policy | Periodic audit cadence and objective D3 gates | Pass with follow-up |
| PM Agent | D2 partial | WBS, pilot checklist, backlog, risks | Real pilot owner, stakeholder map, decision calendar | Needs targeted PM follow-up |
| Chief Architect | D2 | Control/Runtime/Data Plane, closed-net boundaries, extension rules | Architecture fitness tests and deployment validation | Pass for design |
| Security Architect | D2 plus D3 seed | ACL matrix, deny-by-default, audit, prompt injection, cache invalidation rules | Policy tests, threat model drill, audit event validation | ACL retrieval preview started |
| RAG/Data Specialist | D2 strong plus D3 seed | deterministic ingestion, parsing, chunking, metadata, ACL-first retrieval, citation gates | Parser smoke, fake retrieval, ACL/citation golden set | Parser smoke and chunk metadata started |
| AI Runtime Architect | D2 strong plus model policy | Agent Build contract, runtime flow, guards, critic, quality gates, model routing policy | Schema validation, runtime state tests, model gateway route traces | Pass for design, D3 pending |
| Backend Specialist | D2 plus D3 seed | API draft, DB draft, FastAPI skeleton, Alembic migration, audit writer | Contract tests, auth policy, CRUD completeness, run/index job models | Continue immediately |
| Frontend Specialist | D2 | Agent Studio route IA, Builder flow, Test Chat, Run Trace, Eval Dashboard, Open Design review | Implement real Agent Studio views and Playwright smoke | Continue after API contracts firm up |
| DevOps/MLOps | D2 | closed-net topology, release bundle, model serving, backup, monitoring, compose stack | Full compose boot, offline bundle skeleton, smoke scripts | D3 environment validation pending |
| QA/Eval | D2 plus D3 seed | release gates, golden set plan, deterministic scorer design, failure taxonomy, persisted eval report | Eval route metadata and baseline approval review | Continue D3 evidence |

## 3. Key Finding

The team is deep enough in design, but not yet deep enough in verification.

That is expected at this point. The repository has moved from project definition into Sprint 0 implementation. The next orchestrator priority is to convert D2 specialist thinking into D3 executable evidence.

## 4. Required D3 Evidence

| Workstream | Required Evidence |
|---|---|
| PM | pilot owner matrix, document owner list, decision calendar |
| Architecture | service dependency diagram tied to compose and later Helm/offline bundle |
| Security | deterministic ACL tests and audit event field checks |
| RAG/Data | synthetic corpus, parser smoke, chunk metadata validation |
| AI Runtime | Agent Card schema validator and runtime flow state tests |
| Backend | contract tests for `/agents`, `/knowledge`, migrations, audit events |
| Frontend | Playwright smoke for navigation, Builder draft path, Trace placeholder |
| DevOps/MLOps | compose boot smoke, DB migration smoke, offline package manifest draft |
| QA/Eval | eval case JSON/YAML schema, 30 synthetic ACL/citation cases, scorer skeleton |
| Model Routing | shared routing policy, Agent Card model policy, route trace in eval/runtime logs |

## 5. Immediate Dispatch

The orchestrator should now dispatch the next work in this order:

1. Backend + QA: turn Sprint 0 metadata APIs into contract-tested D3 evidence.
2. QA + RAG + Security: create synthetic corpus v0.1 with ACL/citation expected results.
3. Frontend: turn Agent Studio shell into first operator workflow using mocked API data if needed.
4. DevOps: run full compose boot and add smoke instructions or scripts.
5. PM: close pilot owner and document owner placeholders.

## 6. Dispatch Progress

| Dispatch | Status | Evidence |
|---|---|---|
| Backend + QA API contract tests | Expanded | `apps/api/tests/test_metadata_contracts.py` covers detail, patch, validate, publish |
| QA + RAG + Security synthetic corpus | Started | `eval/synthetic-corpus/cases-v0.1.json` |
| QA + RAG + Security deterministic scorer | Started | `eval/harness/run_synthetic_eval.py` |
| RAG + Security fake retrieval ACL tests | Started | `eval/harness/tests/test_fake_retrieval.py` |
| RAG + Security ACL retrieval preview API | Started | `POST /api/v1/knowledge/retrieval/preview` filters unauthorized documents |
| Backend + RAG + QA index job skeleton | Started | `index_jobs`, `document_chunks`, and TXT/MD parser smoke |
| Backend + RAG + Security fake vector adapter | Started | `apps/api/app/domain/vector.py` requires ACL-filtered search |
| AI Runtime + Backend runtime trace API | Hardened | `POST /api/v1/runs` stores model route metadata, skips generation without citations, and maps generator traces to `answer_generator` |
| Audit Explorer API | Started | `/api/v1/audit/events` lists and filters persisted audit events |
| Eval Trace Viewer entry point | Started | `/eval` can sync selected case runtime evidence from `/runs/{run_id}`, `/steps`, and `/retrieval-hits` |
| DevOps compose smoke | Verified | `tools/smoke/compose-smoke.ps1 -Boot -WebPort 0` passed |
| Frontend route/workflow smoke | Expanded | `apps/web/tests/smoke.spec.ts` covers 13 route, workflow, semantics, and mobile checks |
| Eval report persistence | Started | `/api/v1/eval/runs`, `/overview`, latest/result reads, baseline approval audit |
| Agent model routing policy | Hardened | Shared contract, Agent Card config validation, eval route validation, and runtime route summary contract test |
| PM owner closure | Pending | pilot department and document owner still open |

## 7. Acceptance Rule

A specialist workstream can be called "deep" only when it has both:

- D2 artifact: domain-specific rules, risks, alternatives, and acceptance criteria.
- D3 evidence: executable test, review gate, runbook smoke, or measurable report.

By that rule, Agent Forge is currently D2-deep across most domains and D3-started in backend/dev foundation only.
