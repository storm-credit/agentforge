# Agent Forge Product Charter

Status: Draft baseline for Architecture Recovery  
Owner: PM Orchestrator  
Related Epic: #108

## 1. Product Definition

Agent Forge is a governed AI agent builder for closed-network enterprise environments.

The first product boundary is an internal document RAG agent builder that combines approved models, permission-aware knowledge sources, controlled runtime policies, citations, and audit-ready execution traces.

### One-line definition

> 사내망에서 승인된 모델·문서·권한정책·감사 로그를 조합해 근거 기반 업무 에이전트를 만들고 운영하는 통제형 Agent Builder.

### 30-second explanation

Agent Forge allows an operator to register internal documents, configure an agent, publish an approved version, and let employees ask questions. Retrieval is filtered by document permissions before context reaches the model. Answers require citations, and the full execution path is retained for review and audit. The MVP deliberately avoids autonomous write actions and focuses on proving controlled, explainable execution.

## 2. Problem

Enterprise teams can build RAG demos quickly, but production adoption is blocked when the system cannot prove:

- which model and agent version produced an answer;
- whether unauthorized documents were excluded before generation;
- which source supports each material claim;
- whether policy and security checks ran;
- who changed an agent, document permission, or deployment configuration;
- whether a release passed repeatable evaluation gates.

Agent Forge treats those controls as product capabilities rather than optional operational documentation.

## 3. Target Users

| User | Primary need |
|---|---|
| Platform operator | Create, validate, publish, and inspect governed agents |
| Knowledge owner | Register documents, define access policy, and manage lifecycle |
| Employee user | Receive useful answers based only on authorized internal knowledge |
| Security auditor | Verify access control, policy decisions, and trace evidence |
| QA/Eval owner | Run regression suites and block unsafe releases |
| Infrastructure operator | Deploy and operate the platform in a closed network |

## 4. MVP Outcome

The MVP proves one controlled end-to-end loop:

```text
Register document
→ apply ACL and index
→ create and publish an agent version
→ ask a question
→ retrieve authorized context only
→ generate a cited answer or refuse
→ inspect run trace and audit evidence
```

### MVP success criteria

- Unauthorized document leakage: 0 blocker cases.
- Citation-required answers meet the release threshold.
- No-context and unauthorized requests safely refuse.
- Run, retrieval, policy, and audit evidence is reproducible.
- Core operator workflow passes E2E validation.
- The application can be moved to approved internal model endpoints through configuration rather than business-logic rewrites.

## 5. Scope

### Current product scope

- Agent registry and version lifecycle.
- Knowledge source and document ingestion.
- Permission-aware retrieval.
- Citation-based RAG answers and safe refusal.
- Runtime traces and audit events.
- Agent Studio operator flows.
- Deterministic QA/Eval harness and CI/E2E safety net.

### Pilot scope

- One pilot department.
- 30–100 owner-approved internal documents.
- Real SSO/IdP principal context.
- Approved internal LLM, embedding model, and reranker where available.
- Closed-network staging deployment.
- Pilot-specific quality, latency, and operational evidence.

### Explicit non-goals for the first pilot

- Fully autonomous multi-agent execution.
- ERP, groupware, email, calendar, or database write actions.
- Arbitrary external SaaS model or tool access.
- Unregistered MCP servers or tools.
- Automatic processing of confidential documents without an explicit approval policy.
- Self-modifying prompts, policies, agent contracts, or security rules.

## 6. Product Principles

1. **Permission before relevance** — authorization is applied before retrieval candidates reach the model.
2. **Evidence before confidence** — a fluent answer without valid evidence is a failure.
3. **Versioned execution** — agent, model, prompt, knowledge snapshot, and policy references are traceable.
4. **Deny or refuse safely** — absence of authorized evidence must not become model improvisation.
5. **Human authority for consequential actions** — future write tools require preview, approval, audit, and rollback policy.
6. **Closed-network portability** — model and infrastructure adapters must support approved internal services.
7. **Measured completion** — completion claims require tests, evaluation, review, or deployment evidence.
8. **No scope expansion by specialists** — product scope is governed by the PM Orchestrator and recorded decisions.

## 7. Product Boundaries

Agent Forge has two separate orchestration concerns:

| Layer | Meaning | Pilot treatment |
|---|---|---|
| Project delivery orchestration | How PM and specialist agents plan, implement, review, and verify Agent Forge | Version-managed through the repository harness |
| Product runtime orchestration | How a published Agent Forge agent retrieves knowledge, calls approved tools/models, and records evidence | Controlled RAG flow in the first pilot |

The project delivery harness is not itself the end-user runtime. Development MCP tools must not automatically become product runtime tools.

## 8. Current Decision State

### Technical state

- Technical MVP: eligible for GO based on existing code, tests, evaluation, and E2E evidence.
- Pilot entry: HOLD until organizational and infrastructure decisions are supplied.

### Required pilot decisions

- Pilot department and accountable business owner.
- Document owners and real document set.
- SSO/IdP integration choice and credentials.
- Approved internal model and reranker availability.
- Closed-network staging environment.
- Retrieval/rerank configuration baseline decision.

## 9. Change Control

A change to product scope requires:

1. a documented problem or pilot need;
2. impact analysis across security, architecture, data, runtime, operations, and evaluation;
3. an ADR or equivalent decision record when architecture or policy changes;
4. measurable acceptance criteria;
5. PM Orchestrator approval before implementation.

## 10. Next Baseline Artifacts

- Capability Map: Current / Pilot / Later.
- C4 architecture and deployment views.
- Domain model and lifecycle state machines.
- Trust boundaries and product/development MCP separation.
- Requirement-to-evidence traceability matrix.
- Pilot Decision Pack.
