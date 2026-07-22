# Agent Forge Architecture Decision Register

Status: Draft decision baseline  
Owner: Product Architect / PM Orchestrator  
Related: #108, #112

## 1. Purpose

This register records architecture decisions that are already adopted by the repository and decisions that remain unresolved before pilot or later expansion.

It is not a substitute for full ADR documents. It provides one index with status, owner, decision boundary, evidence, and the trigger for creating or updating a detailed ADR.

## 2. Status Definitions

| Status | Meaning |
|---|---|
| `ADOPTED` | The repository consistently relies on the decision; later change requires an ADR and migration/compatibility plan |
| `PROVISIONAL` | Direction is accepted for the technical MVP, but pilot/environment evidence may refine implementation |
| `PROPOSED` | A recommended decision awaiting accountable review |
| `OPEN` | Required decision has no accepted option yet |
| `DEFERRED` | Intentionally postponed because it is outside the current product/pilot boundary |
| `SUPERSEDED` | Replaced by a later decision; history remains linked |
| `REJECTED` | Considered and not selected; rationale must remain discoverable |

## 3. Adopted and Provisional Decisions

| ID | Decision | Status | Owner | Current rationale/evidence | Change trigger |
|---|---|---|---|---|---|
| ADR-001 | Product boundary is a governed internal document RAG agent builder for closed-network enterprise environments | `ADOPTED` | PM Orchestrator | Product Charter, Capability Map, Scope/Non-goals | Approved product-scope expansion |
| ADR-002 | Architecture is logically separated into Control, Runtime, Data, Model, and Delivery planes | `ADOPTED` | Product Architect | Existing architecture plus C4 baseline | Component ownership or trust boundary changes |
| ADR-003 | Authorization is applied before relevance and before model context construction | `ADOPTED` | Security & Trust Architect | ACL retrieval tests/eval and product principles | Never relaxed; implementation change requires security ADR |
| ADR-004 | Missing identity, authorization, required evidence, or required audit follows fail-closed or safe-refusal behavior | `ADOPTED` | Security & Trust Architect | Security model, evaluation plan, current runtime behavior | Any proposed fail-open exception |
| ADR-005 | Published Agent Versions and Builds are immutable; changes create new versions/builds | `ADOPTED` | Product Architect / Backend | Agent Build Spec and version lifecycle | Versioning model or mutable runtime configuration proposal |
| ADR-006 | Build identity resolves prompts, models, policies, tools, and Index Snapshot references | `PROVISIONAL` | AI Architect / Backend | Agent Build Spec | Full runtime enforcement and persistence validation |
| ADR-007 | PostgreSQL is the authoritative transactional metadata, trace, audit, and evaluation store | `ADOPTED` | Backend / Platform | Implementation plan and migrations | Store split, event store, or external audit sink proposal |
| ADR-008 | Vector DB is a derived search index, not the authority for document ACL or ownership | `ADOPTED` | RAG/Data / Security | Vector adapter and ACL design | New search technology or metadata authority proposal |
| ADR-009 | Raw documents/artifacts use an object-store abstraction; metadata/checksum lineage remains in the domain store | `PROVISIONAL` | Platform / RAG/Data | MinIO-oriented implementation plan | Target environment storage decision |
| ADR-010 | Model access is mediated by a Model Gateway/adapter and approved routing policy | `ADOPTED` | AI Platform / Runtime | Current routing implementation and Agent Build Spec | New provider, direct model access, or routing authority change |
| ADR-011 | Reranking receives only already-authorized chunks | `ADOPTED` | Security / RAG | Retrieval invariant | Never relaxed; reranker topology changes require verification |
| ADR-012 | Technical MVP, Pilot, and Production Ready are distinct readiness states | `ADOPTED` | PM Orchestrator / Release Governor | Product Glossary and Current State | Readiness/governance policy change |
| ADR-013 | Development orchestration and product runtime orchestration are separate trust and product boundaries | `ADOPTED` | PM Orchestrator / Security | Product Charter, Scope, Delivery Harness | Any proposal to reuse development agents/tools at runtime |
| ADR-014 | Development MCP is not automatically Product MCP; product tools require a Product Tool Contract and Registry approval | `ADOPTED` | Security / Runtime-MCP | Product baseline and harness principles | Product MCP integration work |
| ADR-015 | Consequential product write tools are excluded from the first pilot | `ADOPTED` | Product / Security | Scope and Non-goals | A separately approved write-tool use case |
| ADR-016 | Evaluation evidence supports but does not automatically make release decisions | `ADOPTED` | QA/Eval / Release Governor | Evaluation plan and glossary | Automated release authority proposal |
| ADR-017 | Review/rewrite/retry loops are bounded and escalate after repeated failure | `ADOPTED` | PM Orchestrator / Runtime | Harness baseline and Agent Build Spec | Loop-policy tuning or autonomous runtime expansion |
| ADR-018 | Closed-network deployment blocks outbound internet by default and uses controlled artifact import | `ADOPTED` | Platform / Security | Existing architecture and deployment baseline | Target network/security architecture change |
| ADR-019 | Logical components may remain co-located in the technical MVP; service separation requires operational justification | `PROVISIONAL` | Product Architect / Platform | Current FastAPI/Next.js topology | Scale, isolation, ownership, or reliability evidence |
| ADR-020 | Repository documents and schemas are the durable source for delivery-harness policy, not conversational memory or ignored local folders | `ADOPTED` | PM Orchestrator | Harness foundation | Provider-specific harness implementation work |

## 4. Open Pilot Decisions

| ID | Decision required | Status | Accountable owner | Options to evaluate | Evidence required | Blocks |
|---|---|---|---|---|---|---|
| ADR-101 | Pilot department and accountable business owner | `OPEN` | Sponsor / Product Owner | Candidate departments/use cases | Named owner, user group, measurable outcome, risk acceptance | Pilot scope and GO |
| ADR-102 | Pilot document inventory, owners, classification, ACL, and retention | `OPEN` | Business Owner / Knowledge Owners / Security | 30–100 owner-approved documents or revised bounded corpus | Inventory, owner approvals, group mapping, retention and deletion rules | Real-corpus ingestion/eval |
| ADR-103 | Enterprise SSO/IdP integration | `OPEN` | Security / Platform | OIDC, SAML gateway, reverse-proxy identity, approved alternative | Trusted claims, group semantics, session/token policy, failure tests | Pilot identity and ACL |
| ADR-104 | Internal chat LLM endpoint and operating owner | `OPEN` | AI Platform | Approved internal serving options | Model/version, capacity, latency, data policy, support and fallback | Pilot runtime |
| ADR-105 | Internal embedding endpoint/model | `OPEN` | AI Platform / RAG | Approved internal models | dimensions, language quality, throughput, versioning, migration strategy | Pilot indexing/retrieval |
| ADR-106 | Reranker model and whether pilot baseline uses reranking | `OPEN` | RAG/Data / QA-Eval | no reranker, cross-encoder, approved alternative | real-corpus quality/latency comparison and operational ownership | Retrieval baseline / Config-C |
| ADR-107 | Vector backend for closed-network staging | `OPEN` | Platform / RAG/Data | Qdrant, pgvector | ACL query contract, backup/restore, capacity, operations skill, offline packaging | Staging deployment |
| ADR-108 | Object storage implementation | `OPEN` | Platform | MinIO-compatible, approved internal object store, filesystem with controls | access, checksum, backup/restore, retention, HA | Staging ingestion |
| ADR-109 | Closed-network staging topology and namespace ownership | `OPEN` | Platform / Security | Compose-like, Kubernetes/Helm, approved VM platform | network zones, secrets, ingress, storage, capacity, support | Pilot deployment |
| ADR-110 | Audit retention, access, redaction, and optional external internal-audit sink | `OPEN` | Security / Compliance / Platform | PostgreSQL only, dedicated internal sink, hybrid | classification, retention period, append controls, access review, capacity | Pilot operations/compliance |
| ADR-111 | Backup, restore, RTO, and RPO | `OPEN` | Platform / Business Owner | Environment-supported options | restore test, dependency ordering, accepted RTO/RPO | Pilot operations |
| ADR-112 | Monitoring, alerting, incident, and on-call ownership | `OPEN` | Platform / Service Owner | Existing internal stack and team model | SLOs, alert routes, runbooks, escalation, ownership | Pilot operations |
| ADR-113 | Pilot release approvers and separation of duties | `OPEN` | Sponsor / Security / Release Governor | Named accountable roles | RACI, approval authority, emergency disable and rollback | Pilot GO/HOLD/NO-GO |
| ADR-114 | Config-C retrieval/rerank/evaluation baseline | `OPEN` | Product / RAG / QA-Eval | Existing candidate configurations | fixed corpus, metrics, latency, regression report, decision rationale | Final pilot baseline |

## 5. Open Architecture-Recovery Decisions

| ID | Decision required | Status | Owner | Recommendation | Acceptance evidence |
|---|---|---|---|---|---|
| ADR-201 | Canonical naming and directory for new architecture baselines | `PROPOSED` | Product Architect | `docs/10-architecture/` with old docs retained as source/history | Index links and reviewer agreement |
| ADR-202 | Canonical ADR file template and numbering | `PROPOSED` | Product Architect | One file per consequential decision under `docs/30-decisions/`, register as index | Template, ownership, supersede rules |
| ADR-203 | Agent Contract schema format | `OPEN` | PM Orchestrator / Product Architect | JSON Schema with YAML instances | Schema validation and example agents |
| ADR-204 | Work Order, Review Result, and Evidence Package schema format | `OPEN` | Delivery Harness / QA-Eval | JSON Schema with YAML/JSON instances | Validation tests and one end-to-end work packet |
| ADR-205 | Provider-neutral Hook policy versus provider adapters | `PROPOSED` | Delivery Harness | Normative policy in repository; Claude/Codex/etc. adapters subordinate | Testable hook fixtures and no provider-only guarantee |
| ADR-206 | Development MCP registry representation | `OPEN` | Security / Delivery Harness | Versioned registry with tool/server owner, risk, permissions, side effects, approvals | Schema, examples, pre-use enforcement strategy |
| ADR-207 | Model routing policy artifact | `OPEN` | AI Architect / Runtime | Versioned policy separate from provider configuration | Schema, route tests, trace linkage |
| ADR-208 | Requirement-to-evidence traceability storage | `PROPOSED` | PM Orchestrator / QA-Eval | Versioned matrix in `docs/40-delivery/` plus generated reports later | Reviewable IDs and maintenance rule |
| ADR-209 | Whether `current-state.md` becomes accepted SSOT rather than candidate | `PROPOSED` | PM Orchestrator | Accept after architecture/harness baseline convergence | Document authority review and index update |

## 6. Deferred Expansion Decisions

These decisions are intentionally deferred and do not belong in active implementation until product scope changes.

| ID | Topic | Status | Re-entry trigger |
|---|---|---|---|
| ADR-301 | Autonomous multi-agent product runtime | `DEFERRED` | Approved user problem and safety/evaluation design |
| ADR-302 | ERP/manufacturing write tools | `DEFERRED` | Approved domain use case, human approval, idempotency, rollback, audit design |
| ADR-303 | Email/calendar/groupware write tools | `DEFERRED` | Approved draft/preview/confirmation use case and identity/security design |
| ADR-304 | Operational database query/write tools | `DEFERRED` | Read-only replica/allowlist or write-control architecture approved |
| ADR-305 | Public multi-tenant SaaS | `DEFERRED` | New product strategy, tenancy, compliance, billing, and public-cloud architecture |
| ADR-306 | External SaaS models/tools | `DEFERRED` | Separate security and network-transfer approval |
| ADR-307 | Organization-wide automatic document discovery | `DEFERRED` | Data-governance, owner, classification, ACL, and retention program |
| ADR-308 | Agent marketplace/domain pack distribution | `DEFERRED` | Product ownership, trust, package signing, compatibility, and support model |

## 7. ADR Creation Rule

A full ADR is required when a change:

- changes product scope or a NON-GOAL;
- changes an authoritative data store or aggregate boundary;
- crosses or changes a trust boundary;
- changes identity, ACL, policy, audit, retention, or fail-closed behavior;
- introduces a Product Tool/MCP server or side effect;
- changes Agent Version/Build immutability or lifecycle;
- changes model/vector/object-store provider in a way that affects contracts or operations;
- changes release gates or readiness meaning;
- creates a new independently deployed service;
- accepts a material risk or irreversible migration.

Minor implementation choices that do not affect these boundaries may be documented in design notes or Work Orders without a full ADR.

## 8. ADR Template

```markdown
# ADR-NNN: Decision title

Status: Proposed | Adopted | Rejected | Superseded
Date: YYYY-MM-DD
Owners: ...
Related requirements/issues/PRs: ...
Supersedes / Superseded by: ...

## Context
Problem, constraints, evidence, and decision deadline.

## Decision Drivers
- ...

## Options Considered
### Option A
Benefits, costs, risks.

### Option B
Benefits, costs, risks.

### Do nothing / defer
Consequences.

## Decision
Selected option and exact boundary.

## Consequences
Positive, negative, migration, operational, security, and evaluation effects.

## Required Controls and Evidence
Tests, evals, trace, monitoring, rollback, review, approvals.

## Follow-up
Owned actions with due/trigger conditions.
```

## 9. Register Maintenance

- Every ADR ID is stable and never reused.
- A changed decision is superseded; prior rationale remains.
- The owner updates status when the decision is accepted, rejected, or deferred.
- PRs implementing an ADR link the ADR and required evidence.
- Traceability work maps requirements and Release Gates to adopted ADRs.
- The Independent Release Governor verifies that release claims do not depend on unresolved blocking ADRs.