# Agent Forge Delivery Hook Policy

Status: Draft harness baseline  
Owner: Delivery Harness / Security & Trust Architect  
Related: #108, #120

## 1. Purpose

Hooks provide deterministic lifecycle controls around model-assisted delivery work. They load authoritative context, validate tool actions, trigger checks, require evidence, and stop unsafe or unbounded execution.

Repository policy is normative. Provider-specific adapters may implement these semantics, but a conversational prompt, provider setting, or experimental hook type is not the sole source of a guarantee.

Machine-readable baseline: `harness/hooks/policy.yaml`.

## 2. Principles

1. Hooks enforce repository policy; they do not create new product scope.
2. Deterministic command or policy checks are preferred for blocking guarantees.
3. Model/prompt-based hooks may advise but do not replace branch, permission, schema, CI, or security controls.
4. Development hooks do not become Product Runtime authorization controls.
5. A hook must be testable using fixtures and expected allow/block/escalate outcomes.
6. Hook failure follows the declared fail-closed or advisory policy.
7. Secrets and classified payloads are minimized and redacted in hook input/output.
8. Every block identifies the violated rule and the safe next action.

## 3. Lifecycle Events

### 3.1 SessionStart

Purpose: establish authoritative context before planning or tool use.

Required load order:

1. `docs/00-product/product-charter.md`
2. `docs/00-product/capability-map.md`
3. `docs/00-product/scope-and-non-goals.md`
4. `docs/40-delivery/current-state.md`
5. active Work Order
6. applicable architecture/security/ADR/traceability documents
7. Specialist Agent Contract
8. approved model/tool registries and loop budget

Checks:

- repository and branch are identified;
- only one active slice is selected;
- current branch is not protected `main` for modification;
- Work Order status and role assignment are valid;
- missing required decisions/dependencies are surfaced before implementation;
- prior Evidence Package or unresolved findings are loaded when continuing work.

Block conditions:

- no active Work Order for implementation;
- ambiguous repository/branch/candidate;
- requested work contradicts an explicit NON-GOAL;
- role is not authorized for requested resource boundary.

### 3.2 PreToolUse

Purpose: decide whether a proposed tool action is allowed before side effects.

Evaluation inputs:

- actor/specialist role;
- Work Order ID and active scope;
- tool/server/version and registry boundary;
- target repository/path/environment/system;
- read/write/destructive/external-transfer classification;
- parameters normalized for policy checks;
- branch and protected-resource status;
- required approval and action hash;
- credential/network boundary;
- attempt/loop budget.

Hard blocks:

- direct protected-branch write;
- unregistered Development MCP or Product Tool;
- development credential/tool used against Product Runtime or production resources;
- secret or credential written to prompts, logs, repository, artifacts, or user output;
- destructive action without explicit human approval;
- production action without an exact authorized Work Order and human authority;
- path/target outside the Work Order;
- consequential Product Tool in first-pilot scope;
- command or action with an unbounded target;
- user/model-provided identity accepted as trusted authority;
- attempt exceeding loop budget without escalation.

Approval-required examples:

- delete/force-update/close-without-resolution;
- protected branch or release action;
- production or account mutation;
- credential/permission changes;
- consequential write Tool preview execution;
- irreversible migration/cleanup;
- changing a blocker threshold or security policy.

### 3.3 PostToolUse

Purpose: validate the result and trigger checks appropriate to the change.

Checks are impact-based:

| Change | Required checks |
|---|---|
| Markdown/docs | link/authority/scope review; readiness claims; changed-file boundary |
| JSON/YAML/schema | parse and schema validation; examples validate; compatibility review |
| Backend | format/lint, unit/integration, auth/audit impact, migration checks |
| Frontend | typecheck, component tests, permission/error states, E2E impact |
| Migration | forward and rollback/forward-fix evidence, concurrency/data integrity |
| Security/ACL | negative authorization, leakage, redaction, fail-closed cases |
| RAG/eval | affected corpus, citation/refusal/leakage regression, missing cases |
| Platform | artifact digest, secret scan, egress, deployment/restore checks |
| Tool/MCP | contract/schema, permission, replay, timeout, unknown-effect, audit tests |

Result handling:

- expected success produces a verification record;
- unexpected result creates a finding with severity and failure attribution;
- partial/unknown side effect stops automatic retry;
- output containing suspected secrets is quarantined/redacted and escalated;
- a changed file outside scope blocks further modification until PM review.

### 3.4 SubagentStop

Purpose: validate a Specialist Agent's completion claim before returning work to the orchestrator.

Required questions:

1. Were all assigned deliverables produced?
2. Do acceptance criteria have evidence?
3. Did the specialist stay inside authority and scope?
4. Are tests/evals linked to the exact candidate?
5. Are limitations and deferred decisions explicit?
6. Did any blocker/critical finding remain open?
7. Were required reviewers identified?
8. Was the loop budget respected?
9. Did the specialist modify product scope or policy without authority?
10. Is a human decision required?

Outcomes:

- `accept_for_review` — deliverables/evidence complete;
- `changes_required` — bounded rework remains within budget;
- `hold` — dependency/decision/authority/evidence missing;
- `escalate` — repeated failure, blocker, scope conflict, unknown effect, or human authority needed.

### 3.5 Stop

Purpose: decide whether the orchestrated slice may end.

The slice stops only when:

- Work Order acceptance criteria pass;
- required reviews have an acceptable outcome;
- Evidence Package identifies exact candidate and fresh evidence;
- limitations and non-code blockers are recorded;
- traceability/ADR/doc authority are updated where affected;
- no blocker remains inside approved scope;
- PR and required CI/merge decision are complete for repository work;
- the approved queue is exhausted or next slice is explicitly activated.

The slice must stop with HOLD/escalation when:

- product/pilot/security/production authority is missing;
- same failure occurs twice without a new bounded hypothesis;
- formal rework budget is exhausted;
- evidence is missing/stale/conflicting;
- scope expansion is required;
- an unknown/partial external effect exists;
- a NON-GOAL would need to change;
- continuing would only generate low-impact nits without measurable outcome.

## 4. Enforcement Levels

| Level | Meaning | Suitable mechanisms |
|---|---|---|
| Block | Action must not proceed | branch protection, permission check, command hook, registry/schema validator, policy engine |
| Approval required | Action pauses for accountable human decision | exact-action approval workflow |
| Escalate | Agent stops and supplies evidence/options | orchestrator/human handoff |
| Warn | Non-blocking risk/advice | deterministic warning or reviewer note |
| Observe | Record for evidence and tuning | structured trace/metrics |

Security, identity, protected-branch, secret, unregistered-tool, and consequential-side-effect controls are not merely warnings.

## 5. Provider Adapter Requirements

A provider adapter documents:

- supported lifecycle events;
- which normative rules are hard blocks versus advisory due to platform limitations;
- command/policy implementation references;
- input/output redaction;
- timeout/failure behavior;
- fixture tests;
- gaps requiring branch protection, CI, external policy, or human procedure.

Provider-specific experimental agent hooks may be used for advice or review, but production-grade guarantees prefer deterministic commands and external enforcement.

## 6. Hook Fixture Matrix

Minimum fixtures:

- allowed feature-branch documentation write;
- blocked direct `main` write;
- blocked out-of-scope path;
- blocked unregistered MCP server;
- blocked development tool against product/production target;
- blocked secret-like output;
- destructive action requiring approval;
- schema file triggering parser/schema checks;
- backend change triggering backend/migration/security checks;
- ACL change triggering leakage cases;
- partial Tool effect triggering escalation and no retry;
- missing Work Order at SessionStart;
- repeated same failure triggering escalation;
- low-impact nit after acceptance triggering stop;
- complete Evidence Package allowing stop.

## 7. Audit and Evidence

Each blocking or approval-required decision records:

- event and policy version;
- actor role and Work Order;
- tool/version and normalized target;
- allow/block/approval/escalate decision;
- reason code;
- action hash where applicable;
- timestamp and correlation;
- redacted evidence reference.

Hook traces are delivery evidence. They do not replace Product Runtime Audit Events.