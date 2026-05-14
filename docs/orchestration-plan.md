# Orchestration Plan

Agent Forge is managed as an orchestrated expert workflow rather than a single chatbot build. The orchestrator coordinates PM, architecture, security, AI runtime, RAG, backend, frontend, DevOps/MLOps, and QA/Eval workstreams.

The operating model is: the orchestrator governs direction and gates; specialist agents perform deep domain work. See [Agent Operating Model](agent-operating-model.md).

Model usage is also orchestrated. Specialist and runtime agents must follow [Agent Model Routing Policy](agent-model-routing-policy.md), which fixes when work stays deterministic, when a small model is enough, and when deep-review reasoning is mandatory.

## Current Objective

Create an explainable project package for the first MVP: an internal document-based RAG agent builder for closed-network environments.

## Gates

| Gate | Exit Criteria |
|---|---|
| G0 Project Definition | One-line definition, 30-second explanation, and non-scope are documented |
| G1 MVP Scope | Use case, success criteria, and excluded scope are fixed |
| G2 Security First | ACL, audit, PII, and prompt-injection controls are defined before implementation |
| G3 Architecture | Control Plane, Runtime Plane, and Data Plane are mapped to services |
| G4 RAG | Ingestion, ACL-aware retrieval, citation, and evaluation are connected |
| G5 Implementation | API, DB, UI, deployment, and QA plans are aligned with the MVP |

## Expert Workstreams

- PM: proposal, use case, WBS, risks
- Architecture: system boundaries and deployment units
- Security: ACL, threat model, audit policy
- AI Runtime: agent build schema and workflow
- RAG/Data: document pipeline and retrieval policy
- Backend: APIs, tables, jobs, audit storage
- Frontend: Agent Studio flows
- DevOps/MLOps: closed-network deployment and observability
- QA/Eval: success criteria and regression set

## Model-Aware Dispatch

The orchestrator assigns each dispatch with both a specialist owner and a model route:

| Dispatch Type | Default Route | Escalation |
|---|---|---|
| routine document cleanup, checklist sync, UI copy | `fast-small` | `standard-rag` if acceptance criteria changes |
| API, DB, runtime, RAG, eval implementation | `standard-rag` | `deep-review` for migration, auth, audit, release gates |
| ACL, PII, prompt injection, audit, model policy | `deep-review` | no downgrade without explicit orchestrator decision |
| synthetic eval scoring and smoke checks | `deterministic` first | `deep-review` only for failed-case triage |

The dispatch is not complete until the expected D3 evidence is named: contract test, smoke run, eval report, runbook, or release-gate decision.

## Depth Expectation

Specialist agents should operate at D2 or higher:

- D2 means deep specialist work with domain rules, risks, alternatives, and acceptance criteria.
- D3 means implementation verification against tests, security policy, and release gates.

The MVP does not assume fully autonomous multi-agent execution yet. The project first proves the controlled workflow through docs, backlog, code, tests, and audit-ready design.

## Principle

The MVP proves controlled execution first: permission-aware retrieval, cited answers, and traceable audit logs. ERP, groupware, and write-action automation are deferred to later system tool packs.
