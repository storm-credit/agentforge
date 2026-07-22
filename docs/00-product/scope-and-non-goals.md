# Agent Forge Scope and Non-Goals

Status: Draft product baseline  
Owner: PM Orchestrator  
Related: #108, #110

## 1. Scope Statement

Agent Forge is a governed internal document RAG agent builder for closed-network enterprise environments.

The first product and pilot boundary is deliberately narrow: an accountable operator registers approved internal documents, configures and publishes a versioned agent, and allows authenticated employees to ask questions. The runtime retrieves only authorized evidence, produces cited answers or refuses, and records execution and audit evidence.

The repository may contain architecture ideas, adapters, experimental panels, or future integration notes. Those items are not product scope unless this document, the Product Charter, and the Capability Map classify them as such.

## 2. In Scope — Technical MVP

The technical MVP includes:

- agent registry and version lifecycle;
- knowledge source and document registration;
- document parsing, chunking, indexing, and retrieval;
- permission-aware retrieval before model context construction;
- approved model-routing abstraction;
- citation-based answer generation;
- safe refusal when authorized evidence is absent;
- run, retrieval, policy, route, and audit traces;
- operator-facing Agent Studio and audit/evaluation views;
- deterministic evaluation, CI, and E2E safety nets;
- adapter-oriented model and vector-store integration;
- closed-network-oriented deployment design.

Technical MVP inclusion means the capability is implemented within the repository evidence boundary. It does not by itself mean real-pilot, production, security-accreditation, or enterprise-operations readiness.

## 3. In Scope — First Pilot

The first pilot adds environment and organizational proof to the technical MVP:

- one named pilot department and accountable business owner;
- named knowledge owners;
- approximately 30–100 approved internal documents;
- real SSO/IdP principal and group context;
- approved internal LLM, embedding model, and reranker configuration;
- closed-network staging deployment;
- real-corpus ACL, citation, refusal, quality, latency, and capacity evidence;
- audit retention and access rules;
- backup, restore, monitoring, alerting, incident, and support ownership;
- a documented human GO/HOLD/NO-GO decision.

The pilot is a controlled validation, not a promise of company-wide rollout.

## 4. Conditional Scope

The following may be implemented only when they directly close a first-pilot blocker or a critical security, integrity, evaluation, or deployment risk:

- SSO/IdP integration work;
- internal model, embedding, or reranker adapters;
- closed-network deployment and offline promotion work;
- real-document ingestion corrections;
- ACL or identity mapping fixes;
- evaluation changes required by the real pilot corpus;
- operational evidence and release-gate implementation;
- security or data-integrity remediation;
- defects that break current technical MVP evidence.

Conditional scope requires a linked requirement, accountable owner, acceptance criteria, and evidence plan. It is not a general exemption from the feature freeze.

## 5. Explicit Non-Goals — First Pilot

### 5.1 Autonomous execution

The first pilot does not include:

- fully autonomous multi-agent planning and execution;
- agents that create or modify their own prompts, policies, contracts, or security rules;
- unbounded retry, reflection, critic, or delegation loops;
- automatic release decisions without accountable human approval;
- hidden actions that cannot be reconstructed from traces.

### 5.2 Consequential write tools

The first pilot does not include write access to:

- ERP or manufacturing systems;
- databases;
- groupware;
- email or calendar;
- file servers;
- source-control repositories;
- ticketing, approval, purchasing, HR, or financial systems.

Future write tools require a separate product decision and must define identity, authorization, preview, human approval, bounded targets, idempotency, timeout, failure behavior, audit, rollback, and ownership.

### 5.3 Unrestricted MCP and tools

The first pilot does not include:

- arbitrary user-added MCP servers;
- automatic exposure of development MCP tools to product users;
- tools without an approved owner and version;
- tools without input/output schemas, data classification, risk level, side-effect declaration, audit behavior, and fail-closed rules;
- production access inherited from a developer workstation or conversational session.

### 5.4 External and public SaaS operation

The first pilot does not include:

- unrestricted external model APIs;
- arbitrary internet access from the runtime;
- a public multi-tenant SaaS offering;
- cross-customer data processing;
- multi-region public-cloud availability commitments;
- consumer-facing agent distribution or marketplace functions.

### 5.5 Broad enterprise knowledge coverage

The first pilot does not include:

- company-wide document ingestion;
- automatic confidential-document discovery;
- ingestion without a named owner;
- treating file-system visibility as authorization;
- bypassing ACL for retrieval quality;
- unsupported document types added solely to increase demo coverage.

### 5.6 Product claims outside evidence

The project must not claim:

- production readiness based only on local, synthetic, or CI evidence;
- pilot readiness without real identity, documents, models, staging, and operational ownership;
- enterprise security accreditation unless formally granted;
- guaranteed factual correctness because citations exist;
- general agent-platform equivalence with broader commercial products;
- committed roadmap status for items classified as `LATER-CANDIDATE`.

## 6. Later Candidates — Not Commitments

The following are possible future directions, not approved backlog commitments:

- read-only enterprise Tool Packs;
- ERP, database, groupware, email, calendar, file-server, or Git integrations;
- approval-based write actions;
- autonomous or multi-agent runtime patterns;
- adaptive retrieval and advanced memory;
- organization-wide catalog and governance;
- multi-tenant administration;
- public SaaS deployment;
- agent marketplace or reusable business-domain packs.

A later candidate enters product scope only through the scope-change process.

## 7. Development Harness Boundary

The delivery harness governs how Agent Forge is designed, implemented, reviewed, and verified. It may include PM orchestration, specialist agents, Skills, Hooks, work orders, evidence packages, and development MCP tools.

The delivery harness is not automatically part of the user-facing Agent Forge runtime.

Therefore:

- a development tool is not a product tool;
- a specialist agent is not an end-user runtime agent;
- a repository hook is not a production authorization control;
- a successful conversational workflow is not reproducible evidence until encoded in versioned assets;
- development credentials and permissions must never flow into the product runtime by default.

## 8. Backlog Admission Rule

A proposed item may enter the active backlog only when all of the following are true:

1. It supports the approved technical MVP, first pilot, or a critical risk remediation.
2. It has a named accountable owner.
3. It identifies the affected product capability and lifecycle classification.
4. It includes measurable acceptance criteria.
5. It identifies security, data, runtime, deployment, and evaluation impact.
6. It specifies required evidence.
7. It does not contradict an explicit non-goal.
8. PM Orchestrator approval is recorded.

Ideas that fail these conditions belong in an idea register, not the implementation queue.

## 9. Scope Change Process

Changing this boundary requires:

1. a documented user, pilot, compliance, or operational problem;
2. alternatives, including doing nothing;
3. value and cost analysis;
4. architecture and trust-boundary impact;
5. data classification and authorization impact;
6. failure, audit, and rollback design where side effects exist;
7. evaluation and release-gate changes;
8. an ADR or equivalent decision record;
9. accountable human approval;
10. updates to the Product Charter, Capability Map, this document, and traceability assets.

Implementation must not begin before the scope decision is accepted.