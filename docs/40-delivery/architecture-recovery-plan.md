# Architecture Recovery & Harness Productization Plan

Status: Repository recovery COMPLETE; First-pilot decision phase HOLD  
As of: 2026-07-22  
Owner: PM Orchestrator  
Related: #108, #122

## 1. Objective

Re-establish design authority over the existing Agent Forge implementation without discarding working code.

The recovery is complete for repository product, architecture, security, traceability, release, and delivery-harness assets. The existing technical MVP was preserved. No application rewrite was initiated.

Completion of this plan does not mean a real pilot or production deployment is approved. Pilot Entry remains HOLD until the accountable inputs in the Pilot Decision Pack are supplied and verified.

## 2. Recovery Principles

1. Preserve the existing working MVP.
2. Freeze speculative feature expansion during Pilot HOLD.
3. Use explicit product, architecture, security, schema, decision, and evidence assets before implementation.
4. Run one bounded slice at a time.
5. Use impact-based specialist review rather than full-panel repetition.
6. Separate Delivery orchestration from Product Runtime.
7. Keep provider-specific adapters subordinate to versioned provider-neutral policy.
8. Do not derive Pilot or Production readiness from synthetic/repository evidence alone.
9. Require an accepted Work Order before implementation.
10. Require candidate-specific Evidence Packages and bounded loops.

## 3. Completion Summary

| Phase | Result | Primary artifacts | Merged PR |
|---|---|---|---:|
| Phase 0 — Authority foundation | COMPLETE | Product Charter, Current State candidate, recovery plan, Harness README/manifest | #109 |
| Phase 1 — Product baseline | COMPLETE | Capability Map, Scope/Non-goals, Glossary | #111 |
| Phase 2A — Architecture baseline | COMPLETE | C4, Domain Model, State Machines, ADR Register | #113 |
| Phase 2B — Trust and MCP | COMPLETE | Trust/data flows, Tool/MCP Governance, Tool Contract, registries | #115 |
| Phase 3 — Traceability and delivery control | COMPLETE | Requirement matrix, Release Gates, Evidence Package guide/schema | #117 |
| Phase 4 — Harness contracts and specialists | COMPLETE | Agent/Work/Review/Routing schemas, ten roles, model policy | #119 |
| Phase 5 — Skills, Hooks, engineering loops | COMPLETE | seven Skills, Hook policy/manifest, Design/Build/Eval/Ops loops, algorithm guidance | #121 |
| Phase 6A — Recovery convergence | IN FINAL REVIEW | Pilot Decision Pack, accepted Current State, completion report | Convergence PR |
| Phase 6B — Real pilot decisions and implementation | HOLD | ADR-101 through ADR-114 decisions and target evidence | Not activated |

## 4. Completed Deliverables

### Product baseline

- [x] Product Charter.
- [x] Capability Map split into CURRENT-PROVEN, CURRENT-LIMITED, PILOT-REQUIRED, LATER-CANDIDATE, and NON-GOAL.
- [x] Scope and Non-Goals.
- [x] Product Glossary.
- [x] Backlog admission and scope-change rules.

### Architecture baseline

- [x] C4 System Context.
- [x] C4 Container view.
- [x] logical Component views for Control, Runtime, Data, Model, and Delivery planes.
- [x] closed-network Deployment view.
- [x] Domain Model and aggregate ownership.
- [x] state machines for Agent Version, Build, Knowledge Source, Document, Index Job/Snapshot, Run, Tool Invocation, Approval, Eval Run, and Release Decision.
- [x] Trust Boundary and Data Flow model.
- [x] ADR Register.
- [x] Model Routing Policy.
- [x] bounded Agentic Algorithm Pattern guidance.

### Traceability and delivery control

- [x] Requirement → authority/ADR → component → implementation/evidence → test/evaluation matrix.
- [x] PR, Technical MVP, Pilot Entry/Exit, and Production Release Gates.
- [x] Evidence Package Guide and schema.
- [x] Pilot Decision Pack.
- [x] Current State accepted as authoritative SSOT after convergence.
- [x] Recovery Completion Report.

### Harness foundation

- [x] Harness Manifest and README.
- [x] Agent Contract schema.
- [x] Work Order schema.
- [x] Review Result schema.
- [x] Tool Contract schema.
- [x] Evidence Package schema.
- [x] Model Routing Policy schema and provider-neutral policy.
- [x] ten Specialist Agent definitions.
- [x] Development MCP Registry.
- [x] deny-by-default Product Tool Registry.
- [x] Loop budgets and escalation policy.
- [x] completion-claim and Evidence Package policy.

### Skills, Hooks, and loops

- [x] Product Baseline Review Skill.
- [x] Architecture Decision Review Skill.
- [x] Threat Modeling Skill.
- [x] RAG Evaluation Design Skill.
- [x] API Contract Review Skill.
- [x] Migration Verification Skill.
- [x] Release Governance Skill.
- [x] SessionStart policy.
- [x] PreToolUse policy.
- [x] PostToolUse policy.
- [x] SubagentStop policy.
- [x] Stop policy.
- [x] machine-readable Hook policy manifest.
- [x] bounded Design Loop.
- [x] bounded Build Loop.
- [x] bounded Eval Loop.
- [x] bounded Operations Loop.
- [x] bounded Review Loop.

## 5. Exit Criteria Assessment

| Criterion | Result |
|---|---|
| Existing application behavior preserved | PASS — recovery PRs changed only `docs/` and `harness/` assets |
| Product boundary explicit | PASS |
| Capability/readiness levels distinguishable | PASS |
| Architecture component/data/state authority explicit | PASS |
| Security controls tied to data flows | PASS |
| Development MCP separated from Product Runtime | PASS |
| Product Tools deny-by-default and contract-governed | PASS |
| Release claim reviewable without full Git-history interpretation | PASS |
| Non-code blockers classified and visible | PASS |
| Specialist authority and prohibited actions versioned | PASS |
| Work cannot validly move into build without acceptance criteria | PASS as repository policy/schema |
| Loops have budgets, stop, revert/defer, and escalation | PASS |
| New model/provider can recover context from repository assets | PASS for baseline documents/contracts |
| Provider-specific deterministic enforcement implemented | NOT CLAIMED — future bounded implementation |
| Harness schemas/examples validated automatically in CI | NOT CLAIMED — future bounded implementation |
| Real-pilot inputs and evidence complete | FAIL/OPEN — Pilot HOLD |

## 6. Specialist Review Model

| Change type | Required review roles |
|---|---|
| Product scope or pilot outcome | PM Orchestrator, Product Architect, accountable human owner, Release Governor |
| Trust boundary, ACL, identity, Tool/MCP permission | Security & Trust, affected architecture/runtime owner, QA/Eval |
| Retrieval, chunking, embedding, rerank, citation, refusal | RAG/Data, QA/Eval, Security when access is affected |
| API/domain/migration | Backend, Product Architect, QA/Eval, Security when authorization/data is affected |
| Operator/approval workflow | Frontend, PM/Product, Security, QA/Eval |
| Deployment/offline import/recovery | Platform, Security, QA/Eval, Service Owner |
| Cross-domain architecture | Product Architect plus all affected specialists |
| Merge/release/pilot claim | Independent Release Governor and accountable human roles |

A full panel is reserved for cross-domain, trust-boundary, or convergence decisions. Low-impact nits do not keep a bounded slice open.

## 7. Loop Termination

A slice ends when:

- its bounded deliverables are complete;
- acceptance checks pass;
- required reviews decide;
- Evidence Package pins exact candidate and fresh evidence;
- limitations and deferred decisions are explicit;
- no blocker remains inside the accepted scope;
- merge/release decision is complete;
- no next task is automatically activated.

Default budgets:

- specialist self-review: 2 passes;
- formal-review implementation rework: 1 pass;
- repeated same failure: human escalation after 2 occurrences;
- runtime answer rewrite/critic: 1 pass unless an approved policy says otherwise;
- parallel mutable workspaces: prohibited unless isolation is proven;
- low-impact nit without security, integrity, pilot, evidence, operations, or user-correctness effect: backlog;
- automatic next task after the accepted queue is exhausted: none.

## 8. Remaining Enforcement Work — Not Automatically Activated

Potential later bounded Work Orders may implement:

- CI validation for Harness JSON/YAML schemas and examples;
- provider-specific deterministic Hook adapters;
- Work Order/Review/Evidence generation and validation tooling;
- Traceability consistency checks;
- registry validation and product Tool Executor conformance before any Tool activation;
- model-routing policy integration validation.

These are Harness enforcement improvements, not Product feature commitments. They require accepted Work Orders and must not be used to bypass Pilot HOLD.

## 9. Pilot Decision and Implementation Release

Real pilot work is not activated until applicable decisions are accepted:

- ADR-101 pilot department/business owner/users/outcome;
- ADR-102 approved document inventory/owners/classification/ACL/retention;
- ADR-103 real SSO/IdP;
- ADR-104 chat LLM;
- ADR-105 embedding model;
- ADR-106 reranker/no-reranker;
- ADR-107 vector backend;
- ADR-108 object store;
- ADR-109 closed-network staging;
- ADR-110 audit policy;
- ADR-111 backup/restore RTO/RPO;
- ADR-112 monitoring/incident/on-call;
- ADR-113 release roles;
- ADR-114 Config-C retrieval/rerank/eval baseline.

After decisions exist, implementation proceeds as one Work Order per direct blocker with specialist review, target-environment evidence, and Pilot Entry gates.

## 10. Final Convergence Rule

After the convergence PR passes required Backend, Frontend, and Playwright E2E CI and is merged:

1. this plan becomes COMPLETE for repository recovery;
2. `current-state.md` becomes the authoritative Current-State SSOT;
3. Epic #108 may close as completed for Architecture Recovery and Harness Productization;
4. Pilot Entry remains HOLD;
5. no application task is automatically created;
6. the next legitimate action is to complete the Pilot Decision Pack with named accountable humans and accepted ADR decisions.