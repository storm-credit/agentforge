# Orchestration Plan

Agent Forge is managed as an orchestrated expert workflow rather than a single chatbot build. The orchestrator coordinates PM, architecture, security, AI runtime, RAG, backend, frontend, DevOps/MLOps, and QA/Eval workstreams.

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

## Principle

The MVP proves controlled execution first: permission-aware retrieval, cited answers, and traceable audit logs. ERP, groupware, and write-action automation are deferred to later system tool packs.
