# Agent Forge Current State

Status: Authoritative Current-State SSOT  
As of: 2026-07-22  
Owner: PM Orchestrator  
Related: #108, #122

## 1. Purpose and Authority

This document is the concise source of truth for what Agent Forge currently supports, what remains blocked, and what work is allowed next.

- `docs/00-product/*` owns product purpose, capability classification, scope, non-goals, and terminology.
- `docs/10-architecture/*`, `docs/20-security/*`, and `docs/30-decisions/*` own architecture, security, lifecycle, Tool/MCP, and decision baselines.
- `docs/40-delivery/*` owns traceability, gates, evidence, pilot decisions, and current execution policy.
- `docs/status-and-go-no-go.md` remains detailed historical implementation and panel evidence.
- `notes/01_PM/WBS.md` remains the original planning baseline, not current completion authority.
- `CLAUDE.md` remains a provider-specific repository execution rule set subordinate to the versioned product/harness baseline.

When historical plans or status logs conflict with current delivery status, this document takes precedence.

## 2. Executive Status

| Area | Status | Meaning |
|---|---|---|
| Product boundary | ACCEPTED | Closed-network Governed Internal Document RAG Agent Builder |
| Technical MVP | GO-capable | Core controlled RAG loop is implemented and backed by repository tests/evaluation evidence |
| Architecture Recovery | COMPLETE | Product, C4/domain/state, trust/MCP, ADR, traceability, gate, and convergence assets are versioned |
| Harness Productization | COMPLETE — repository foundation | Contracts, roles, Skills, Hooks policy, loops, registries, routing, and evidence assets exist; provider adapters/CI validators remain implementation work |
| First real pilot | HOLD | Accountable business, document, identity, model, environment, operations, and release inputs remain open |
| Production readiness | NOT ASSESSED | Target-environment and organizational evidence does not exist and must not be inferred |
| Speculative features | FROZEN | Only direct pilot blockers or critical security/integrity/deployment/evaluation defects may enter accepted Work Orders |
| Application rewrite | NOT PLANNED | Existing implementation is preserved |

## 3. Working Technical MVP Boundary

The repository supports the intended controlled loop:

```text
register/upload an approved document
→ parse, chunk, embed, and index
→ apply ACL-aware retrieval before relevance
→ create, validate, and publish an Agent Version
→ execute a question for a Principal
→ produce a cited answer or safe refusal
→ inspect Run, retrieval, route, citation, policy, and audit evidence
```

Current implementation/evidence areas include:

- FastAPI backend and Next.js Agent Studio;
- PostgreSQL domain, lifecycle, Run, audit, and evaluation persistence;
- Qdrant-compatible vector retrieval with authorization filters;
- configurable model gateway/routing abstractions;
- Agent and Agent Version lifecycle;
- document ingestion, indexing, ACL, revoke/delete, and retrieval paths;
- Run Steps, Retrieval Hits, citations, route traces, and Audit Events;
- backend tests, migration round-trip validation, frontend type checking, and Playwright E2E in CI;
- deterministic and API-backed evaluation harnesses.

This describes repository technical capability. It does not prove real SSO, real documents, approved internal models, target staging, operations, pilot acceptance, or production readiness.

## 4. Accepted Product and Architecture Decisions

- Product position: governed internal document RAG Agent Builder.
- Technical MVP, Pilot, and Production Ready are distinct states.
- Authorization is applied before relevance, reranking, and model context.
- Missing identity, authorization, required evidence, or required audit follows deny/fail-closed/safe-refusal behavior.
- Published Agent Versions and Builds are immutable.
- PostgreSQL metadata/policy is authoritative; vector storage is a derived search index.
- Model access uses approved, classification-aware, traceable routes with no silent external fallback.
- Development orchestration and Product Runtime are separate trust and product boundaries.
- Development MCP does not automatically become Product MCP.
- Product Tools require versioned contracts, registry approval, authorization, risk, side-effect, approval, audit, idempotency, and failure/compensation rules.
- Consequential write Tools are excluded from the first pilot.
- Automated tests/evaluation provide evidence; accountable humans record GO/HOLD/NO-GO.
- Review/retry/reflection loops are bounded and stop after their approved budget.

## 5. Architecture Recovery and Harness Assets

### Product

- Product Charter;
- Capability Map;
- Scope and Non-Goals;
- Product Glossary.

### Architecture and security

- C4 Context/Container/Component/Deployment baseline;
- Domain Model and aggregate ownership;
- Agent/Build/Document/Index/Run/Tool/Approval/Eval/Release state machines;
- Model Routing Policy;
- Agentic Algorithm Pattern adoption boundaries;
- Trust Boundaries and Data Flows;
- Tool and MCP Governance;
- ADR Register.

### Delivery and evidence

- Requirement Traceability Matrix;
- Release Gates;
- Evidence Package Guide and schema;
- Pilot Decision Pack;
- Recovery Completion Report.

### Harness

- Harness Manifest and README;
- Agent Contract, Work Order, Review Result, Tool Contract, Evidence Package, and Model Routing schemas;
- ten Specialist Agent contracts;
- Development MCP and Product Tool registries;
- provider-neutral Hook policy and machine-readable rule manifest;
- bounded Design, Build, Eval, Operations, and Review loops;
- seven reusable Skills;
- Work Order and Evidence Package examples.

## 6. First-Pilot Blockers

| ADR | Required decision/input | Accountable owner | Status | Unlocks |
|---|---|---|---|---|
| ADR-101 | Pilot department, business owner, users, measurable outcome | Sponsor / Product Owner | OPEN | Defined pilot candidate and authority |
| ADR-102 | Approved documents, owners, classification, ACL, retention/deletion | Business / Knowledge Owners / Security | OPEN | Real corpus ingestion and security/quality evaluation |
| ADR-103 | Enterprise SSO/IdP and trusted group/role claims | Security / Platform | OPEN | Real Principal and authorization evidence |
| ADR-104 | Approved internal chat LLM | AI Platform | OPEN | Representative generation quality, latency, failure evidence |
| ADR-105 | Approved internal embedding model | AI Platform / RAG | OPEN | Target indexing/retrieval baseline |
| ADR-106 | Reranker or approved no-reranker decision | RAG/Data / QA-Eval | OPEN | Stable authorized reranking baseline |
| ADR-107 | Vector backend | Platform / RAG/Data | OPEN | Target ACL query, operations, backup, capacity evidence |
| ADR-108 | Object storage | Platform | OPEN | Approved document storage and recovery |
| ADR-109 | Closed-network staging topology | Platform / Security | OPEN | Installation, network, secret, capacity, deployment evidence |
| ADR-110 | Audit retention/access/redaction/sink | Security / Compliance / Platform | OPEN | Pilot audit and compliance evidence |
| ADR-111 | Backup/restore, RTO/RPO | Platform / Business Owner | OPEN | Recovery gate |
| ADR-112 | Monitoring, alerts, incidents, on-call, SLOs | Platform / Service Owner | OPEN | Operability and support gate |
| ADR-113 | Release approvers and separation of duties | Sponsor / Security / Release Governor | OPEN | Accountable Pilot GO/HOLD/NO-GO |
| ADR-114 | Config-C retrieval/rerank/evaluation baseline | Product / RAG / QA-Eval | OPEN | Fixed real-corpus candidate and thresholds |

Current Pilot Entry outcome: **HOLD**.

## 7. Work Allowed Next

No application slice is automatically activated by completing Architecture Recovery.

A new accepted Work Order may be created only for:

1. a directly approved pilot blocker supported by the applicable ADR decision;
2. real SSO/IdP integration;
3. approved real-document and ACL onboarding;
4. approved internal model/vector/object/staging integration;
5. audit, retention, backup, monitoring, controlled-import, or operational controls required for Pilot Entry;
6. real-corpus security, quality, performance, or capacity remediation;
7. a reproducible security vulnerability or unauthorized data exposure;
8. data corruption or lifecycle-integrity failure;
9. a deployment/migration blocker;
10. an evaluation, trace, audit, citation, refusal, or approved-MVP regression defect;
11. bounded harness enforcement such as schema validation or provider-specific deterministic Hook adapters, when separately accepted and not used to disguise product feature work.

Every implementation Work Order requires:

- requirement IDs and applicable ADRs;
- explicit included/excluded scope;
- assigned specialist roles;
- measurable acceptance criteria;
- security/data/architecture impact;
- verification and affected Eval Cases;
- required Review Results;
- Evidence Package;
- loop budget, stop, rollback/disable, and human escalation.

## 8. Work Not Allowed Without Scope Change

- autonomous multi-agent Product Runtime;
- ERP, database, email, calendar, groupware, file-server, source-control, finance, access-control, or production write actions;
- arbitrary or user-added MCP servers;
- Development MCP/credentials exposed to Product Runtime;
- external SaaS model/Tool fallback;
- company-wide automatic document discovery;
- self-changing prompts, policies, contracts, permissions, or security rules;
- general platform breadth without a named owner and pilot outcome;
- broad rewrite or service decomposition without evidence;
- repeated expert-panel/nit work without security, integrity, pilot, evidence, operations, or user-correctness impact.

## 9. Gate Rules

### Technical MVP

GO-capable means repository evidence supports preparation for a pilot. It does not mean target-environment or business acceptance.

### Pilot Entry

Pilot GO requires all applicable Pilot Entry gates, including:

- named accountable owners and users;
- approved document inventory and ACL;
- real SSO/IdP;
- approved internal models and Config-C baseline;
- closed-network staging;
- zero mandatory ACL leakage;
- accepted citation/refusal/quality and performance evidence;
- audit/retention/access controls;
- backup/restore and RTO/RPO;
- monitoring, alerts, incidents, on-call, runbooks;
- controlled artifact import;
- named release approvers and an exact Pilot Entry Evidence Package.

### Release blockers

- unauthorized data exposure;
- untrusted identity accepted as authorized;
- ACL filter absent/bypassed;
- forbidden content reaching reranker/model/response/trace/log;
- missing required citation/support or refusal behavior;
- unregistered Product Tool/MCP execution;
- consequential action without exact approval, idempotency, audit, and effect verification;
- silent external model/Tool route;
- required audit failure reported as success;
- mutable published Build;
- missing/falsified blocker evidence;
- required CI/migration/E2E failure;
- real pilot activation with any mandatory owner/data/identity/model/environment/release input missing.

## 10. Known Recovery Limitations

The repository baseline is complete, but the following enforcement remains future bounded implementation:

- automated CI validation for all harness JSON/YAML schemas and examples;
- provider-specific deterministic Hook adapters;
- generated Work Order/Review/Evidence tooling;
- automated traceability consistency checks;
- registry and model-routing conformance validators.

These limitations do not change Pilot HOLD and do not authorize speculative product features.

## 11. Next Decision

The next valid project action is not “continue coding.” It is:

1. name the accountable pilot owners;
2. complete the Pilot Decision Pack and applicable ADR-101 through ADR-114 decisions;
3. create one accepted Work Order per direct blocker;
4. implement and evaluate in closed-network staging;
5. assemble a candidate-specific Pilot Entry Evidence Package;
6. obtain independent review and accountable GO/HOLD/NO-GO.

Until step 1 begins, the safe state is: **technical MVP preserved, feature freeze active, pilot HOLD**.