# Architecture Recovery & Harness Productization Plan

Status: Active  
Owner: PM Orchestrator  
Related Epic: #108

## 1. Objective

Re-establish design authority over the existing Agent Forge implementation without discarding working code.

The recovery converts the repository from a code-led prototype with substantial documentation into a governed product repository where:

- product boundaries are explicit;
- architecture decisions are traceable;
- specialist agents receive bounded work orders;
- MCP, hooks, and skills are governed contracts;
- implementation starts after design approval;
- completion is based on reproducible evidence;
- loop termination is intentional rather than endlessly generating minor work.

## 2. Recovery Principles

1. Preserve the current working MVP.
2. Freeze speculative feature expansion during pilot HOLD.
3. Prefer documentation, decisions, schemas, and evidence over code in recovery slices.
4. Run one slice at a time unless work is demonstrably independent and isolated.
5. Use impact-based specialist review rather than a full panel for every change.
6. Separate development orchestration from product runtime orchestration.
7. Keep provider-specific configuration subordinate to versioned, vendor-neutral repository policy.
8. Do not declare production or pilot readiness from synthetic evidence alone.

## 3. Work Breakdown

### Phase 0 — Stabilize and establish authority

Deliverables:

- Product Charter.
- Current State source of truth.
- Recovery plan.
- Harness README and manifest.
- Documentation index registration.

Exit criteria:

- The Draft PR changes no application behavior.
- Product, current state, and recovery policy do not materially contradict the existing architecture and status evidence.
- Reviewers can identify which document owns product scope, current status, delivery history, execution rules, and harness policy.

### Phase 1 — Product baseline

Deliverables:

- Capability Map split into Current / Pilot / Later.
- Scope and Non-goals register.
- Product glossary.
- Stakeholder and decision-rights map.

Questions to settle:

- Is the pilot product name and market position “Governed RAG Agent Builder” or broader?
- Which operator and end-user roles are required for pilot?
- Which capabilities are product commitments versus demonstrations?
- What is the minimum pilot acceptance package?

Exit criteria:

- No specialist can expand pilot scope without a recorded decision.
- Each pilot capability has an owner and measurable outcome.

### Phase 2 — Architecture baseline

Deliverables:

- C4 Context view.
- C4 Container view.
- C4 Component views for Control, Runtime, and Data planes.
- Closed-network deployment view.
- Domain model.
- Lifecycle state machines.
- Trust-boundary and data-flow model.
- ADR index and open-decision register.

Required lifecycle models:

- Agent and Agent Version.
- Knowledge Source and Document.
- Index Job.
- Runtime Run and Step.
- Tool/MCP registration and approval.
- Evaluation baseline and release decision.

Exit criteria:

- Every runtime and storage component has an owner and trust classification.
- Security controls are tied to explicit data flows.
- Planned product MCP cannot inherit development MCP access by accident.

### Phase 3 — Traceability and delivery control

Deliverables:

- Requirement → ADR → component → code → test → evaluation matrix.
- Release-gate catalog.
- Evidence Package schema.
- Pilot Decision Pack.
- Baseline/version naming policy.

Exit criteria:

- A release claim can be checked without reading the complete Git history.
- Each blocker is classified as code, decision, organization, model, data, or infrastructure.
- Non-code blockers cannot be disguised as implementation backlog.

### Phase 4 — Harness foundation

Deliverables:

- Agent Contract schema and initial specialist definitions.
- Work Order schema.
- Review Result schema.
- Tool Contract schema.
- Model routing policy.
- Loop budgets and escalation policy.
- Completion-claim policy.

Exit criteria:

- A new session or supported model provider can recover the same work context from repository assets.
- Specialist authority and prohibited actions are machine-readable or structurally reviewable.
- Work cannot move from design to build without explicit acceptance criteria.

### Phase 5 — Skills, hooks, and MCP governance

Deliverables:

- Core Skills packages.
- Provider-neutral hook policy.
- Provider-specific hook adapters where useful.
- Development MCP registry.
- Product MCP/Tool Pack contract.
- Side-effect, approval, audit, and rollback policy.

Initial skills:

- product baseline review;
- architecture decision review;
- threat modeling;
- RAG evaluation design;
- API contract review;
- migration verification;
- release governance.

Initial hook policy:

- SessionStart context load.
- PreToolUse protected-resource and tool registration checks.
- PostToolUse format/lint/test/change-impact checks.
- SubagentStop evidence and scope checks.
- Stop decision, evidence, and termination checks.

Exit criteria:

- Unregistered destructive tools are blocked or require explicit human approval.
- Tool definitions include risk, permissions, side effects, audit, and failure behavior.
- Hook behavior can be tested independently from a specific conversational session.

### Phase 6 — Pilot decision and implementation release

Required inputs:

- named pilot owner;
- approved document inventory and owners;
- SSO/IdP decision;
- approved internal model endpoints;
- closed-network staging environment;
- accepted retrieval/rerank/eval configuration baseline.

Only after these inputs are available should the project create implementation slices for pilot-specific gaps.

Exit criteria:

- Pilot GO/HOLD/NO-GO package signed by accountable owners.
- Remaining code work is directly linked to a pilot requirement or blocker.

## 4. Specialist Review Model

| Change type | Required reviewers |
|---|---|
| Product scope or pilot outcome | PM Orchestrator, Product Architect, accountable human owner |
| Trust boundary, ACL, identity, tool permissions | Security & Trust, affected architecture/runtime owner |
| Retrieval, chunking, rerank, citation, eval | RAG/Data, QA/Eval, Security when access is affected |
| API/domain/migration | Backend, QA/Eval, Security when authorization or data is affected |
| Operator workflow | Frontend, PM/Product, QA/Eval |
| Deployment/offline release | Platform, Security, QA/Eval |
| Cross-domain architecture | Product Architect plus all affected specialists |

A full panel is not the default. It is reserved for cross-domain architecture changes, trust-boundary changes, or scheduled convergence reviews.

## 5. Loop Termination

A slice ends when:

- its bounded artifact or implementation is complete;
- defined acceptance checks pass;
- required reviewers have decided;
- limitations and deferred decisions are recorded;
- no unresolved blocker remains inside the approved scope.

A slice does not remain open merely because another minor improvement can be imagined.

Default budgets:

- specialist self-review: 2 passes;
- formal-review implementation rework: 1 pass;
- repeated same failure: human escalation after 2 occurrences;
- low-impact nit without security, integrity, pilot, or evidence effect: backlog;
- no automatic next task when the approved queue is exhausted.

## 6. Immediate Slice Sequence

1. **Foundation PR** — Product Charter, Current State, recovery plan, harness README and manifest.
2. **Product baseline** — Capability Map, Scope/Non-goals, glossary.
3. **Architecture views** — C4, domain model, state machines.
4. **Trust and MCP** — trust boundaries, development/product MCP separation, Tool Contract.
5. **Traceability** — requirements/evidence matrix and release gates.
6. **Agent contracts** — PM and specialist definitions, Work Order and Evidence schemas.
7. **Hook policy** — lifecycle rules and test strategy.
8. **Pilot Decision Pack** — human and infrastructure decisions needed to resume pilot code.

Each slice must be a separate reviewed PR unless combining them materially improves consistency without expanding scope.

## 7. Foundation PR Acceptance Criteria

- [x] Epic #108 exists.
- [x] Architecture Recovery branch exists.
- [x] Product Charter added.
- [x] Current State SSOT candidate added.
- [x] Harness README added.
- [x] Harness manifest added.
- [x] Recovery plan added.
- [ ] Docs index updated.
- [ ] Draft PR opened.
- [ ] No application code changed.
- [ ] Review confirms no false production-readiness claim.
