# Agent Operating Model

Agent Forge uses an orchestra-and-specialist model.

The orchestrator owns direction, gates, sequencing, and integration. Specialist agents own deep work inside their domains. This is not meant to be a loose collection of chat prompts; it is a controlled workflow where every agent has a role, input, output, and acceptance gate.

## 1. Core Answer

Yes: the orchestrator is the general manager.

The orchestrator:

- keeps the MVP scope stable
- assigns work to specialist agents
- checks dependencies and conflicts
- promotes stable drafts from `notes/` into `docs/`
- updates backlog, decision log, and release gates
- blocks work that violates security, audit, or MVP boundaries

Yes: the agents are expected to be deep.

Specialist agents are not just label names. Each agent should carry domain-specific context, checklists, tradeoffs, and output quality rules. A backend agent should reason like a backend owner. A security agent should challenge data exposure and audit gaps. A QA/Eval agent should turn promises into measurable tests.

## 2. Current Reality

There are two layers:

| Layer | Meaning | Current State |
|---|---|---|
| Project orchestration layer | How this repository is planned, designed, implemented, reviewed, and documented | Active now |
| Product runtime layer | How Agent Forge will eventually let users build and operate AI agents | Being built through the MVP |

The repository already uses the project orchestration layer through `notes/00_Orchestrator`, specialist workspaces, official `docs/`, and Sprint 0 code skeleton.

The product runtime layer will become real through Agent Registry, Knowledge ingestion, Runtime runs, evaluation gates, and audit logging.

## 3. Agent Depth Levels

| Level | Name | Expected Behavior |
|---|---|---|
| D0 | Label only | Agent name exists, but output is generic |
| D1 | Structured draft | Agent produces a role-specific draft or checklist |
| D2 | Deep specialist | Agent applies domain rules, risk checks, alternatives, and acceptance criteria |
| D3 | Verifying specialist | Agent can review implementation against tests, policies, and release gates |
| D4 | Operating specialist | Agent remembers decisions, monitors regressions, and updates the system workflow |

Agent Forge should target D2 by default for design work and D3 for implementation/release work. D4 is a later operating goal once telemetry, eval history, and decision memory are wired into the platform.

## 4. Specialist Agent Contracts

| Agent | Owns | Must Produce |
|---|---|---|
| PM Agent | scope, schedule, risk, stakeholder readiness | WBS, pilot checklist, risk log, acceptance criteria |
| Chief Architect | system boundaries and deployment units | control/runtime/data plane architecture, service boundaries |
| Security Architect | ACL, audit, PII, prompt-injection controls | threat model, policy gates, audit requirements |
| AI Runtime Architect | agent schema and runtime flow | agent build spec, execution flow, policy hooks |
| RAG/Data Specialist | ingestion, chunking, retrieval, citation | document pipeline, retrieval rules, eval corpus needs |
| Backend Specialist | APIs, tables, jobs, audit persistence | contracts, migrations, services, test plan |
| Frontend Specialist | Agent Studio workflows | screens, interaction states, operator flows |
| DevOps/MLOps | closed-net deployment and observability | compose, offline packaging, monitoring plan |
| QA/Eval | quality gates and regression evidence | golden set, scoring rubric, release report |

## 5. Dispatch Loop

1. Orchestrator defines the next project objective.
2. Orchestrator assigns a specialist agent and a clear artifact.
3. Specialist agent produces a domain-specific output with assumptions and risks.
4. Adjacent agents review only the parts they own.
5. Orchestrator resolves conflicts and records decisions.
6. Accepted work moves into official docs, backlog, code, or runbooks.

## 6. Guardrails

- No specialist can expand MVP scope without orchestrator approval.
- Security and audit gates can block implementation.
- RAG work cannot bypass ACL filtering.
- Runtime agents cannot use tools that are not registered and risk-rated.
- Draft notes are allowed to be exploratory; official docs must be explainable and actionable.

## 7. Near-Term Implementation

For Sprint 0 and Sprint 1, "deep agents" are represented by:

- role-specific workspaces under `notes/`
- official output docs under `docs/`
- backlog stories with done conditions
- code skeletons tied to those stories
- tests and runbooks that prove each layer is not only described but executable

Later, Agent Forge can turn the same model into product features: agent templates, domain checklists, approval gates, evaluation reports, and audit-backed runtime traces.

