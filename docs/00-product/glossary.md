# Agent Forge Product Glossary

Status: Draft product baseline  
Owner: PM Orchestrator / Product Architect  
Related: #108, #110

## 1. Purpose

This glossary gives product, architecture, delivery, and evaluation terms one repository meaning. Terms used by code may be refined by later domain-model work, but they must not silently contradict these product definitions.

## 2. Core Product Terms

| Term | Repository meaning |
|---|---|
| **Agent Forge** | A governed internal document RAG agent builder for closed-network enterprise environments. It combines approved models, permission-aware knowledge, controlled runtime policy, citations, trace, audit, and evaluation. |
| **Agent** | A governed product definition describing the intended business purpose and allowed behavior. An Agent is not a mutable runtime conversation and is not a development specialist agent. |
| **Agent Version** | A versioned, reviewable configuration of an Agent. It references prompts, model-routing policy, retrieval policy, approved tools, security policy, and other immutable or traceable execution inputs. |
| **Build** | A reproducible package or identity derived from an Agent Version and its referenced prompts, models, tools, policy, and knowledge/index snapshot metadata. A Build is the unit expected to support repeatable execution evidence. |
| **Published Version** | An Agent Version approved for use in a specific environment or audience. Publication does not automatically mean production readiness. |
| **Agent Studio** | The operator-facing control experience for creating, reviewing, publishing, and inspecting governed Agents and their evidence. |
| **Technical MVP** | The repository implementation and automated evidence proving the controlled RAG loop in development and CI conditions. It is not equivalent to real-pilot or production readiness. |
| **Pilot** | A controlled use by one accountable business area with real identity, approved documents, approved internal models, target-environment deployment, and measured operational evidence. |
| **Production Ready** | A status requiring approved environment, security, operations, support, capacity, recovery, monitoring, compliance, and accountable release evidence. It cannot be inferred solely from technical MVP tests. |

## 3. Knowledge and Retrieval Terms

| Term | Repository meaning |
|---|---|
| **Knowledge Source** | A governed logical origin of documents, including ownership, access policy, connector or upload method, lifecycle, and indexing configuration. |
| **Document** | An owner-approved knowledge item registered under a Knowledge Source. A file existing in storage is not automatically an approved Document. |
| **Document Owner** | The accountable person or function authorized to approve ingestion, access rules, lifecycle, and removal for a Document or document set. |
| **Chunk** | A retrieval unit derived from a Document. A Chunk must retain enough source and ACL metadata to support authorized retrieval and citation. |
| **Index** | A searchable representation of approved document chunks for a defined configuration and access model. |
| **Index Snapshot** | A traceable identity or metadata set representing the indexed knowledge state used by a Build or Run. |
| **Index Job** | A stateful operation that parses, chunks, embeds, stores, updates, or removes indexed document content. |
| **Retrieval** | Selection of evidence candidates for a question. Authorization must be applied before unauthorized content can become model context. |
| **Reranking** | Reordering authorized retrieval candidates using an approved scoring model or algorithm. Reranking never grants access. |
| **Context** | The authorized evidence and runtime instructions supplied to the generation model for a Run. |
| **Citation** | A structured reference from an answer to authorized source evidence. A citation supports traceability but does not by itself prove that every statement is correct. |
| **Grounded Answer** | An answer whose material claims are supported by valid authorized evidence under the configured citation policy. |
| **Safe Refusal** | A controlled response produced when authorized evidence is absent, insufficient, or policy prohibits answering. It must not expose unauthorized context or fabricate support. |

## 4. Identity and Security Terms

| Term | Repository meaning |
|---|---|
| **Principal** | The authenticated human or service identity on whose behalf an operation is performed. |
| **SSO/IdP** | The enterprise authentication and identity-provider system supplying trusted principal and group claims. Local or simulated headers are not equivalent to real SSO integration. |
| **ACL** | The access-control rule set that determines which principals or groups may access a Knowledge Source, Document, Chunk, Agent, trace, or administrative action. |
| **Authorization Before Relevance** | The invariant that an item must first be allowed for the Principal before retrieval or ranking considers its semantic relevance. |
| **Trust Boundary** | A boundary across which identity, privileges, data classification, validation, or accountability changes. Crossing it requires explicit controls. |
| **Data Classification** | The approved sensitivity category of data used to determine storage, access, logging, model, connector, and retention rules. |
| **Policy Decision** | A recorded allow, deny, refuse, or approval-required result produced by an applicable security or runtime policy. |
| **Fail Closed** | Behavior that denies or safely refuses when identity, policy, tool, model, or authorization state cannot be validated. |
| **Audit Event** | An immutable or controlled record of a security-relevant or governance-relevant action, actor, target, time, outcome, and associated references. |
| **Approval** | An explicit accountable-human authorization for a bounded action, publication, tool execution, scope change, or release decision. |

## 5. Runtime and Tool Terms

| Term | Repository meaning |
|---|---|
| **Run** | One governed execution of a published Agent Version or Build for a Principal and request, producing steps, evidence, output, policy decisions, and status. |
| **Run Step** | A traceable unit within a Run, such as authorization, retrieval, reranking, model routing, generation, citation validation, tool call, or refusal. |
| **Runtime Trace** | The structured record needed to reconstruct the significant execution path of a Run without exposing secrets or prohibited content. |
| **Model Gateway** | The controlled abstraction that routes approved model requests and records provider, model, policy, latency, failure, and usage metadata. |
| **Model Routing Policy** | The versioned rules that determine which approved model may perform a bounded task under data, quality, capacity, and failure constraints. |
| **Tool** | A bounded callable capability exposed to the product runtime through an approved contract. A Tool may read or cause side effects and must declare risk and authorization requirements. |
| **Tool Contract** | The versioned definition of a Tool, including owner, purpose, schemas, data classification, permissions, risk, side effects, approval, timeout, audit, redaction, failure behavior, idempotency, and rollback where relevant. |
| **Tool Pack** | A governed collection of related Tools approved for a business domain or integration. |
| **Tool Registry** | The authoritative allowlist and metadata catalog of approved product runtime Tools and versions. |
| **MCP** | Model Context Protocol, a protocol that can expose resources, prompts, and tools. In Agent Forge, MCP use is governed by the same authorization, contract, audit, and trust-boundary requirements as any other integration. |
| **MCP Server** | A specific server exposing MCP capabilities. A server available to developers is not automatically approved for product runtime use. |
| **Development MCP** | MCP used by coding or delivery agents to inspect or change project resources. Its credentials and capabilities belong to the delivery trust boundary. |
| **Product MCP** | MCP approved for end-user Agent Forge runtime use under a Product Tool Contract and Product Tool Registry. |
| **Side Effect** | A change outside the immediate model response, including data mutation, message delivery, workflow transition, financial or operational action, or external-system update. |
| **Idempotency** | The property that repeating the same bounded request does not create unintended duplicate effects. |
| **Rollback** | A defined method to safely reverse or compensate for a Tool or deployment effect when technically and operationally possible. |

## 6. Evaluation and Release Terms

| Term | Repository meaning |
|---|---|
| **Eval Case** | A versioned evaluation input with identity, allowed evidence, expected behavior, scoring rules, and severity. |
| **Eval Corpus** | A controlled collection of Eval Cases representing required product and security behavior. |
| **Baseline** | A versioned reference result, configuration, or threshold used to compare a proposed change. |
| **Release Gate** | A mandatory measurable condition that must pass before a Build or release may proceed. |
| **Blocker** | A failure that prevents the applicable release or pilot decision, such as unauthorized data leakage or a required control being absent. |
| **Regression** | A measurable decline from an accepted baseline in security, correctness, quality, performance, reliability, or operability. |
| **Evidence Package** | A structured bundle supporting a completion or release claim, including scope, change, tests, evals, traces, risks, limitations, reviewer decisions, and references. |
| **GO** | The accountable decision that the defined entry criteria for a bounded next stage are satisfied. |
| **HOLD** | The accountable decision that work or entry cannot proceed until named conditions are resolved. |
| **NO-GO** | The accountable decision not to proceed because risk, value, feasibility, or required conditions are unacceptable. |

## 7. Delivery Harness Terms

| Term | Repository meaning |
|---|---|
| **Delivery Harness** | The versioned repository assets and controls governing how Agent Forge work is planned, assigned, implemented, reviewed, evaluated, and terminated. |
| **PM Orchestrator** | The delivery role accountable for product direction, scope, sequence, gate decisions, integration, and escalation. It does not replace accountable human approval. |
| **Specialist Agent** | A bounded delivery role with explicit inputs, outputs, authority, prohibitions, review requirements, and stop conditions. It is not a product runtime Agent. |
| **Agent Contract** | The versioned definition of a Specialist Agent's mission, allowed actions, prohibited actions, inputs, outputs, evidence duties, escalation, and completion conditions. |
| **Work Order** | A bounded assignment describing the problem, approved scope, dependencies, acceptance criteria, evidence, reviewers, and stop conditions. |
| **Review Result** | A structured reviewer decision that records findings, severity, required changes, accepted risks, and outcome. |
| **Skill** | A reusable versioned package of domain instructions, workflows, templates, and checks loaded for a defined delivery task. |
| **Hook** | A deterministic lifecycle control executed at defined delivery events to load context, validate actions, run checks, require evidence, or block unsafe behavior. |
| **Loop Budget** | The maximum permitted review, retry, reflection, or rework cycle before stopping, reverting, deferring, or escalating to a human. |
| **Stop Condition** | An explicit rule ending a task or loop when acceptance is reached, evidence is insufficient, repeated failure occurs, authority is exceeded, or human decision is required. |
| **Release Governor** | An independent delivery role that verifies evidence and gates and records GO, HOLD, or NO-GO recommendations without implementing the change being judged. |

## 8. Classification Terms

| Term | Repository meaning |
|---|---|
| **CURRENT-PROVEN** | Implemented and supported by repeatable repository evidence within a stated boundary. |
| **CURRENT-LIMITED** | Implemented only in a constrained, simulated, local, partial, or configuration-dependent form. |
| **PILOT-REQUIRED** | Required for first-pilot entry but not yet supplied or proven in the target environment. |
| **LATER-CANDIDATE** | A possible future capability that is not an approved commitment or active implementation item. |
| **NON-GOAL** | Explicitly excluded from current scope and prohibited from entering active implementation without scope-change approval. |

## 9. Usage Rules

1. Product documents, issues, work orders, ADRs, schemas, and UI labels should use these terms consistently.
2. A term may be refined by later architecture and domain-model work, but the change must update this glossary and linked documents.
3. Similar terms must not be used to overstate readiness. In particular, `Technical MVP`, `Pilot`, and `Production Ready` are distinct.
4. `Development MCP`, `Specialist Agent`, and `Delivery Harness` must not be described as end-user runtime capabilities.
5. A code identifier may differ for implementation reasons, but documentation must map it to the applicable repository term.