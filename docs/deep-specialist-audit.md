# Deep Specialist Audit

Date: 2026-05-09

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
| Orchestrator | D2.5 | Operating model, dispatch board, ADRs, docs index, Sprint 0 direction | Periodic audit cadence and objective D3 gates | Pass with follow-up |
| PM Agent | D2 partial | WBS, pilot checklist, backlog, risks | Real pilot owner, stakeholder map, decision calendar | Needs targeted PM follow-up |
| Chief Architect | D2 | Control/Runtime/Data Plane, closed-net boundaries, extension rules | Architecture fitness tests and deployment validation | Pass for design |
| Security Architect | D2 | ACL matrix, deny-by-default, audit, prompt injection, cache invalidation rules | Policy tests, threat model drill, audit event validation | Pass for design, D3 pending |
| RAG/Data Specialist | D2 strong | deterministic ingestion, parsing, chunking, metadata, ACL-first retrieval, citation gates | Parser smoke, fake retrieval, ACL/citation golden set | Pass for design, D3 pending |
| AI Runtime Architect | D2 strong | Agent Build contract, runtime flow, guards, critic, quality gates | Schema validation, runtime state tests, mock model gateway | Pass for design, D3 pending |
| Backend Specialist | D2 plus D3 seed | API draft, DB draft, FastAPI skeleton, Alembic migration, audit writer | Contract tests, auth policy, CRUD completeness, run/index job models | Continue immediately |
| Frontend Specialist | D2 | Agent Studio route IA, Builder flow, Test Chat, Run Trace, Eval Dashboard, Open Design review | Implement real Agent Studio views and Playwright smoke | Continue after API contracts firm up |
| DevOps/MLOps | D2 | closed-net topology, release bundle, model serving, backup, monitoring, compose stack | Full compose boot, offline bundle skeleton, smoke scripts | D3 environment validation pending |
| QA/Eval | D2 | release gates, golden set plan, deterministic scorer design, failure taxonomy | Eval case files, runner, automated ACL/citation checks | Must start before Runtime work expands |

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

## 5. Immediate Dispatch

The orchestrator should now dispatch the next work in this order:

1. Backend + QA: turn Sprint 0 metadata APIs into contract-tested D3 evidence.
2. QA + RAG + Security: create synthetic corpus v0.1 with ACL/citation expected results.
3. Frontend: turn Agent Studio shell into first operator workflow using mocked API data if needed.
4. DevOps: run full compose boot and add smoke instructions or scripts.
5. PM: close pilot owner and document owner placeholders.

## 6. Acceptance Rule

A specialist workstream can be called "deep" only when it has both:

- D2 artifact: domain-specific rules, risks, alternatives, and acceptance criteria.
- D3 evidence: executable test, review gate, runbook smoke, or measurable report.

By that rule, Agent Forge is currently D2-deep across most domains and D3-started in backend/dev foundation only.

