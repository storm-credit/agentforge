# Agent Forge Current State

Status: Architecture Recovery SSOT candidate  
As of: 2026-07-22  
Owner: PM Orchestrator  
Related Epic: #108

## 1. Purpose

This document is the concise source of truth for the current delivery state.

- `notes/01_PM/WBS.md` remains the original planning baseline.
- `docs/status-and-go-no-go.md` remains the detailed historical delivery and panel log.
- This file answers what is working now, what is blocked, and what work is allowed next.

When the documents conflict about current status, this file takes precedence after review and merge.

## 2. Executive Status

| Area | Status | Meaning |
|---|---|---|
| Technical MVP | GO-capable | Core governed RAG flow is implemented and backed by tests/evaluation evidence |
| Pilot entry | HOLD | Organizational, identity, model, document, and staging inputs are not complete |
| New product features | FROZEN | Not allowed unless they remove a pilot blocker or critical risk |
| Architecture Recovery | ACTIVE | Product baseline, traceability, harness, and decision control are being formalized |
| Application rewrite | NOT PLANNED | Existing implementation is preserved; recovery is documentation and governance first |

## 3. Working Product Loop

The repository currently supports the following intended MVP path:

```text
Document registration/upload
→ parsing/chunking/indexing
→ ACL-aware retrieval
→ agent creation/version validation/publication
→ question execution
→ cited answer or controlled refusal
→ run/retrieval/audit inspection
```

Existing implementation areas include:

- FastAPI backend and Next.js Agent Studio.
- PostgreSQL metadata, lifecycle, run, and audit persistence.
- Qdrant-compatible vector retrieval with authorization filters.
- Local/internal model gateway configuration.
- Agent version lifecycle.
- Document ACL lifecycle and retrieval enforcement.
- Runtime steps, retrieval hits, citations, and audit evidence.
- CI, backend tests, migration validation, and Playwright E2E.
- Synthetic and live evaluation harnesses.

This list describes current capability, not a promise that production identity, staging deployment, or real pilot content is complete.

## 4. Current Product Boundary

### Allowed in the first pilot

- Internal document RAG.
- Permission-aware retrieval.
- Citation-required answers.
- Controlled refusal.
- Operator-managed agents and knowledge sources.
- Read-oriented, registered capabilities only.
- Trace, audit, evaluation, and release evidence.

### Deferred

- Autonomous multi-agent product runtime.
- ERP/groupware/email/calendar write actions.
- Direct production database mutation.
- Arbitrary MCP server discovery and execution.
- External SaaS model/tool dependencies.
- Self-changing security or agent policy.

## 5. Verified Delivery Strengths

### Governance and architecture

- Control Plane, Runtime Plane, and Data Plane boundaries are documented.
- Specialist roles and D2/D3 depth concepts are documented.
- Sequential slice delivery, PR review, and completion-evidence rules are established.

### Security and data

- ACL-aware retrieval is treated as a pre-retrieval requirement.
- Document permission changes and lifecycle operations are auditable.
- Runtime and administrative authorization gaps have been iteratively hardened.
- Synthetic evaluation includes leakage and refusal cases.

### Quality and operations

- Backend contract and security tests exist.
- Alembic migration checks run against PostgreSQL in CI.
- Frontend E2E runs in CI with deterministic dependencies.
- Evaluation metrics include citation, useful answer, refusal, trace, and latency evidence.

## 6. Known Pilot Blockers

| Blocker | Needed from | Unlocks |
|---|---|---|
| Pilot department and accountable owner | Business/PM | Real pilot plan and acceptance decision |
| Approved real document set and owners | Business/document owners | Real retrieval, permission, and quality evaluation |
| SSO/IdP decision and integration inputs | Security/infrastructure | Trusted principal context and production authorization |
| Approved internal LLM/embedding/reranker | AI infrastructure | Representative quality, latency, refusal, and reranking validation |
| Closed-network staging environment | Platform/infrastructure | Installation, operations, backup, monitoring, and release evidence |
| Retrieval/rerank baseline configuration decision | Product/RAG/QA | Stable pilot configuration and repeatable evaluation baseline |

## 7. Allowed Work Policy

Until pilot inputs are supplied, implementation work is limited to:

- a reproducible security vulnerability;
- unauthorized data exposure;
- data corruption or lifecycle integrity failure;
- a deployment or migration blocker;
- an evaluation or trace correctness defect;
- a regression in an already approved MVP flow;
- architecture recovery and harness productization artifacts.

The following are not automatically code-now work:

- speculative platform breadth;
- additional integrations without a pilot owner;
- aesthetic or low-impact refinements after the operator flow is usable;
- repeated expert-panel nit discovery with no pilot, security, integrity, or evidence impact.

## 8. Architecture Recovery Work

The recovery does not restart development. It adds missing control around the implementation.

### AR-01 Product baseline

- Product Charter.
- Scope and non-goals.
- Capability Map.
- Shared glossary.

### AR-02 Architecture baseline

- C4 views.
- Domain model.
- State machines.
- Trust boundaries.
- ADR register.

### AR-03 Delivery baseline

- Traceability matrix.
- Pilot decision pack.
- Release gates.
- Evidence package rules.

### HP-01 Harness foundation

- Versioned agent contracts.
- Skills and work-order schemas.
- Hook policy.
- Development MCP and product MCP separation.
- Loop budgets and escalation rules.

## 9. Go / Hold Rules

### Technical MVP GO

A technical GO means the controlled synthetic/demo path is sufficiently implemented to prepare a pilot. It does not mean production deployment or business acceptance is complete.

### Pilot GO

Pilot GO requires all of the following:

- named pilot owner and users;
- approved document inventory and ACL mapping;
- SSO principal mapping;
- staging deployment evidence;
- approved model endpoints;
- pilot evaluation baseline and blocker thresholds;
- support and rollback ownership.

### Release blockers

- any unauthorized content exposure;
- missing or misleading audit evidence for a consequential action;
- a required migration or deployment failure;
- a citation-required answer presented without valid support;
- an unregistered tool or MCP execution path;
- a write action without required approval and audit controls.

## 10. Document Authority

| Document | Authority |
|---|---|
| `docs/40-delivery/current-state.md` | Concise current delivery status |
| `docs/00-product/product-charter.md` | Product purpose, boundary, and principles |
| `docs/status-and-go-no-go.md` | Detailed historical evidence and panel chronology |
| `notes/01_PM/WBS.md` | Original planning baseline, not current completion status |
| `CLAUDE.md` | Repository execution rules for supported agent-assisted development |
| `harness/manifest.yaml` | Vendor-neutral harness inventory and loop policy baseline |

## 11. Next Approved Slice

Complete the remaining Architecture Recovery foundation without application changes:

1. add the recovery execution plan;
2. add the repository harness README and manifest;
3. register this new documentation in the docs index;
4. open a Draft PR linked to Epic #108;
5. review before declaring this baseline authoritative.
