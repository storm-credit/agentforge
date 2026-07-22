# Agent Forge Capability Map

Status: Draft product baseline  
Owner: PM Orchestrator / Product Architect  
Related: #108, #110

## 1. Purpose

This map separates what Agent Forge has already demonstrated from what the first real pilot still requires and what is intentionally deferred.

It is a product-planning baseline, not a marketing checklist. A capability is classified as `CURRENT-PROVEN` only when the repository contains implementation and repeatable evidence. A feature shown in a demo, represented by a stub, or planned in a document is not automatically pilot-ready.

## 2. Lifecycle Classifications

| Classification | Meaning | Delivery rule |
|---|---|---|
| `CURRENT-PROVEN` | Implemented and supported by repository tests, evaluation, trace, or E2E evidence | May be treated as part of the technical MVP |
| `CURRENT-LIMITED` | Implemented in a constrained, simulated, local, or configuration-dependent form | Must not be represented as real-pilot ready without closing the stated limitation |
| `PILOT-REQUIRED` | Required for a real departmental pilot but not yet supplied or proven in the target environment | Blocks pilot GO |
| `LATER-CANDIDATE` | A plausible future capability that is outside the first-pilot commitment | Requires a new product decision before design or implementation |
| `NON-GOAL` | Explicitly excluded from the current product and pilot boundary | Must not enter backlog or implementation without an approved scope change |

## 3. Product Position

Agent Forge is currently positioned as a **governed internal document RAG agent builder for closed-network enterprise environments**.

The first pilot is not a general autonomous-agent platform, workflow automation suite, or unrestricted MCP marketplace. It proves one controlled loop: approved internal documents, permission-aware retrieval, cited answers or refusal, versioned execution, evaluation, and audit evidence.

## 4. Capability Map

### 4.1 Product and Agent Lifecycle

| Capability | Classification | Accountable domain | Evidence or limitation |
|---|---|---|---|
| Agent registry | `CURRENT-PROVEN` | Control Plane / Backend | Agent creation and management are implemented in the technical MVP |
| Agent version lifecycle | `CURRENT-PROVEN` | Control Plane / Backend | Versioned configuration and publish-oriented flows exist |
| Immutable build identity | `CURRENT-LIMITED` | AI Architecture / Backend | Build specification exists; full end-to-end enforcement must be traced in later architecture work |
| Operator Agent Studio | `CURRENT-PROVEN` | Frontend / Product | Core operator flows are covered by frontend and E2E evidence |
| Multi-tenant product administration | `LATER-CANDIDATE` | Product / Security | Not required for the first departmental pilot |
| Self-modifying agent definitions | `NON-GOAL` | Product / Security | Prompts, policies, contracts, and security rules require governed human change |

### 4.2 Knowledge and Ingestion

| Capability | Classification | Accountable domain | Evidence or limitation |
|---|---|---|---|
| Knowledge source registration | `CURRENT-PROVEN` | Data / Backend | Source and document ingestion flow exists |
| Document parsing and indexing | `CURRENT-PROVEN` | RAG/Data | Technical MVP and smoke/evaluation flows exist |
| Document lifecycle and re-indexing | `CURRENT-LIMITED` | RAG/Data / Backend | Implemented behavior requires explicit lifecycle/state baseline and real corpus evidence |
| Owner-approved pilot corpus | `PILOT-REQUIRED` | Business Owner / Knowledge Owner | Real departmental documents and owners have not been supplied |
| File server connector | `LATER-CANDIDATE` | Platform / Data | Requires connector, identity, ACL, and operational design |
| Groupware, email, or calendar ingestion | `LATER-CANDIDATE` | Product / Security / Data | Outside first-pilot scope |
| Automatic confidential-document ingestion | `NON-GOAL` | Security / Knowledge Owner | Requires explicit policy and owner approval before any later consideration |

### 4.3 Authorization and Identity

| Capability | Classification | Accountable domain | Evidence or limitation |
|---|---|---|---|
| Permission-aware retrieval | `CURRENT-PROVEN` | Security / RAG | ACL filtering is a core technical MVP invariant and evaluation target |
| Authorization before model context | `CURRENT-PROVEN` | Security / Runtime | Product principle and technical behavior are represented in current implementation and tests |
| Simulated or local principal context | `CURRENT-LIMITED` | Security / Backend | Useful for technical validation but not equivalent to enterprise identity |
| Real SSO/IdP integration | `PILOT-REQUIRED` | Security / Platform | Named identity provider, credentials, group claims, and failure behavior remain unresolved |
| Identity-to-document-group mapping | `PILOT-REQUIRED` | Security / Knowledge Owner | Must be validated with the real pilot organization and document set |
| Cross-organization federation | `LATER-CANDIDATE` | Security / Platform | Not required for the first pilot |
| Bypassing ACL for model quality | `NON-GOAL` | Security | Relevance must never override authorization |

### 4.4 Retrieval, Generation, and Citation

| Capability | Classification | Accountable domain | Evidence or limitation |
|---|---|---|---|
| Vector retrieval abstraction | `CURRENT-PROVEN` | RAG/Data / Backend | Adapter-based retrieval exists with test coverage |
| Permission-filtered vector search | `CURRENT-PROVEN` | Security / RAG | ACL filters are applied within the retrieval path |
| Citation-based answer generation | `CURRENT-PROVEN` | Runtime / RAG | Citation and no-context behavior are evaluated |
| Safe refusal without authorized evidence | `CURRENT-PROVEN` | Runtime / Security | Generation is skipped or refused when usable evidence is absent |
| Approved internal embedding model | `PILOT-REQUIRED` | AI Platform / RAG | Target endpoint and operational ownership remain unresolved |
| Approved internal LLM | `PILOT-REQUIRED` | AI Platform / Runtime | Pilot endpoint, capacity, latency, and support model are unresolved |
| Reranker baseline | `PILOT-REQUIRED` | RAG/Data / QA-Eval | Model and configuration decision remain open |
| Adaptive or agentic retrieval | `LATER-CANDIDATE` | RAG/Data | Requires measurable benefit over the controlled baseline |
| Uncited fluent answers | `NON-GOAL` | Runtime / QA-Eval | Fluency without valid evidence is treated as failure |

### 4.5 Runtime, Trace, and Audit

| Capability | Classification | Accountable domain | Evidence or limitation |
|---|---|---|---|
| Controlled RAG runtime flow | `CURRENT-PROVEN` | Runtime / Backend | Core end-to-end technical loop is implemented |
| Run and step trace | `CURRENT-PROVEN` | Runtime / Backend | Execution and route traces are exposed and tested |
| Audit event exploration | `CURRENT-PROVEN` | Security / Frontend / Backend | Audit surfaces exist in the technical MVP |
| Production-grade log retention policy | `PILOT-REQUIRED` | Security / Platform | Retention, storage capacity, access, and deletion decisions require the target environment |
| Operational alerting and on-call ownership | `PILOT-REQUIRED` | Platform / Operations | Real environment operating model is not yet approved |
| Autonomous multi-agent runtime | `LATER-CANDIDATE` | Product / Runtime / Security | Requires a separate orchestration, safety, and evaluation design |
| Hidden or unaudited tool execution | `NON-GOAL` | Security / Runtime | All consequential actions require trace and policy evidence |

### 4.6 Evaluation and Release Governance

| Capability | Classification | Accountable domain | Evidence or limitation |
|---|---|---|---|
| Deterministic evaluation harness | `CURRENT-PROVEN` | QA/Eval | Corpus, scorer, persistence, and smoke workflows exist |
| ACL leakage gate | `CURRENT-PROVEN` | Security / QA-Eval | Zero blocker leakage is a release invariant |
| Citation and refusal gates | `CURRENT-PROVEN` | QA/Eval / RAG | Threshold-based release checks are defined |
| CI backend, frontend, and E2E checks | `CURRENT-PROVEN` | Platform / QA-Eval | Automated workflows exercise the technical MVP |
| Real-corpus pilot baseline | `PILOT-REQUIRED` | QA/Eval / Business Owner | Synthetic and demo evidence must be supplemented with pilot data |
| Pilot latency and capacity acceptance | `PILOT-REQUIRED` | Platform / AI Platform | Depends on approved internal endpoints and closed-network staging |
| Automatic release without accountable approval | `NON-GOAL` | Release Governor | Evidence informs decisions but does not remove human accountability |

### 4.7 Deployment and Operations

| Capability | Classification | Accountable domain | Evidence or limitation |
|---|---|---|---|
| Local and CI deployment paths | `CURRENT-PROVEN` | Platform | Sufficient for technical development and automated verification |
| Configurable model and vector adapters | `CURRENT-PROVEN` | Backend / Platform | Supports replacement without rewriting core product logic |
| Closed-network staging | `PILOT-REQUIRED` | Platform / Security | Environment, secrets, ingress, storage, and operational controls remain unavailable or undecided |
| Offline dependency and image promotion process | `PILOT-REQUIRED` | Platform / Security | Must be verified in the actual restricted environment |
| Backup, restore, and disaster-recovery acceptance | `PILOT-REQUIRED` | Platform / Operations | Requires environment-specific RTO/RPO decisions |
| Public SaaS multi-region service | `LATER-CANDIDATE` | Product / Platform / Security | Not implied by the closed-network product baseline |
| Arbitrary external SaaS model access | `NON-GOAL` | Security / Product | Only approved internal or explicitly governed endpoints are permitted |

### 4.8 Tools and MCP

| Capability | Classification | Accountable domain | Evidence or limitation |
|---|---|---|---|
| Product Tool Registry concept | `CURRENT-LIMITED` | Runtime / Security | Architecture and policy concepts exist; full contract baseline is a later recovery slice |
| Development MCP usage | `CURRENT-LIMITED` | Delivery Harness | May support project work but is not a product capability |
| Read-only approved product tools | `LATER-CANDIDATE` | Product / Runtime / Security | Requires Tool Contract, allowlist, audit, timeout, and failure policy |
| ERP, database, email, calendar, or groupware write tools | `LATER-CANDIDATE` | Product / Security / Domain Owner | Each integration requires separate value, identity, approval, idempotency, rollback, and audit design |
| Unregistered MCP servers | `NON-GOAL` | Security / Runtime | Product runtime tools must be approved and versioned |
| Development MCP automatically exposed to users | `NON-GOAL` | Security / Delivery Harness | Development and product trust boundaries remain separate |

### 4.9 Delivery Harness and Specialist Work

| Capability | Classification | Accountable domain | Evidence or limitation |
|---|---|---|---|
| PM-orchestrated delivery workflow | `CURRENT-LIMITED` | PM Orchestrator | Existing rules and documents exist; versioned contracts are being productized |
| Specialist role separation | `CURRENT-LIMITED` | PM Orchestrator / Product Architect | Roles exist in documents but machine-readable contracts remain future work in Epic #108 |
| Versioned harness manifest | `CURRENT-LIMITED` | Delivery Harness | Foundation exists; schemas, skills, hooks, and evidence packages remain to be added |
| Work Order and Evidence Package schemas | `PILOT-REQUIRED` for delivery governance | Delivery Harness / QA-Eval | Required before resuming broad implementation work under the new governance model |
| Skills and hook adapters | `LATER-CANDIDATE` within recovery sequence | Delivery Harness | Must follow vendor-neutral policy and be independently testable |
| Development harness marketed as end-user multi-agent runtime | `NON-GOAL` | Product | Project orchestration and product runtime are different systems |

## 5. First-Pilot Capability Set

The first pilot may enter GO review only when the following set is jointly available:

1. Current technical MVP capabilities remain green in CI and evaluation.
2. A named pilot business owner and knowledge owners are accountable.
3. An approved real document inventory is available.
4. Real SSO/IdP identity and group claims are integrated.
5. Approved internal LLM, embedding, and reranker configuration is fixed.
6. Closed-network staging is operational.
7. Real-corpus quality, ACL, citation, refusal, latency, and capacity evidence is collected.
8. Retention, backup, alerting, support, and incident ownership are agreed.
9. Pilot GO/HOLD/NO-GO is signed by accountable humans.

## 6. Change Rule

A capability can move between classifications only when the change includes:

- a linked product or pilot requirement;
- an accountable owner;
- implementation or decision evidence;
- relevant security and architecture impact analysis;
- measurable acceptance criteria;
- an updated traceability record;
- PM Orchestrator approval.

`LATER-CANDIDATE` does not mean committed roadmap. `CURRENT-LIMITED` does not mean pilot-ready. `CURRENT-PROVEN` does not mean production-ready outside the evidence boundary.