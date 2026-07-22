# Agent Forge Bounded Engineering Loops

Status: Draft harness baseline  
Owner: PM Orchestrator / QA-Eval  
Related: #108, #120

## 1. Purpose

Engineering loops turn uncertain work into a bounded sequence of hypotheses, checks, decisions, and evidence. They are not permission to iterate indefinitely.

Every loop begins with an accepted Work Order, preserves one primary variable where practical, records failures, has a budget, and ends in acceptance, revert/defer, HOLD, or human escalation.

## 2. Shared Loop Contract

Every loop declares:

- problem and intended measurable outcome;
- exact candidate/baseline;
- requirement IDs and applicable ADRs;
- allowed resources and prohibited actions;
- owner and required specialist reviewers;
- checks and Evidence Package destination;
- maximum attempts/review passes;
- stop, revert, defer, and escalation conditions.

Default budgets:

| Budget | Default |
|---|---:|
| Specialist self-review | 2 passes |
| Formal-review implementation rework | 1 pass |
| Same failure before human escalation | 2 occurrences |
| Runtime answer rewrite/critic pass | 1, unless an approved policy says otherwise |
| Parallel mutable workspaces | 0 unless isolation is proven |
| Automatic next task after queue exhaustion | 0 |

A new attempt must use a new bounded hypothesis. Repeating the same action without new evidence is not a loop; it is uncontrolled retry.

## 3. Design Loop

### Inputs

- approved product problem and scope;
- current-state evidence;
- affected requirements, components, trust boundaries, and data;
- constraints and deadline/decision trigger.

### Steps

```text
frame problem and non-goals
→ verify current state
→ identify constraints and decision drivers
→ generate alternatives including do-nothing/defer
→ analyze value, security, data, operations, migration, and evaluation impact
→ select or recommend an option
→ record ADR/contract/state changes
→ specialist review
→ freeze accepted design for the Work Order
```

### Gates

- product scope authority exists;
- current behavior is verified rather than assumed;
- trust/data/identity effects are explicit;
- alternatives and negative consequences are recorded;
- acceptance criteria and evidence are measurable;
- unresolved human decisions cause HOLD, not invented defaults.

### Stop conditions

- accepted design and Work Order are ready;
- no option is acceptable within scope;
- product/organization/security authority is missing;
- new scope or trust boundary requires separate decision;
- two design passes produce no material improvement.

## 4. Build Loop

### Inputs

- accepted Work Order and frozen design;
- requirement/state/API/schema contracts;
- test/eval plan;
- isolated feature branch/worktree.

### Steps

```text
create failing test or reliable reproduction
→ implement minimal bounded change
→ run focused checks
→ run broader impacted checks
→ inspect diff for scope and security
→ specialist self-review
→ formal review
→ bounded rework once
→ assemble Evidence Package
→ merge decision
```

### Rules

- One primary behavior/failure is addressed per slice where practical.
- Refactoring unrelated code is excluded unless required for the accepted change.
- A failing test is not deleted or weakened merely to pass.
- Migration, authorization, audit, failure, and rollback behavior are first-class acceptance criteria when affected.
- Shared mutable environment damage stops the loop and triggers environment recovery before code work continues.

### Revert/defer

Revert or defer when:

- measurable gain is absent and complexity/risk increases;
- the accepted design is invalidated;
- required testability cannot be achieved safely;
- the change depends on missing organization/data/model/infrastructure input;
- the same failure repeats twice without a new hypothesis;
- formal rework remains unacceptable.

## 5. Evaluation Loop

### Inputs

- pinned baseline and candidate;
- exact corpus, identity/ACL, models, Index Snapshot, policies, and environment;
- metrics, blocker cases, and attribution categories.

### Steps

```text
freeze baseline and corpus
→ state one change/hypothesis
→ run deterministic and required model-assisted evaluation
→ compare case-level and aggregate results
→ attribute failures
→ inspect blockers and missing cases
→ adopt, revert, or revise one bounded variable
→ record baseline decision and evidence
```

### Rules

- ACL leakage and other blockers are absolute; aggregate improvement cannot offset them.
- Missing/unavailable cases are incomplete evidence.
- Difficult cases are not removed to improve scores.
- Real-corpus and synthetic evidence remain labeled separately.
- Threshold changes require before/after distributions, rationale, risk, and accountable review.
- One variable changes per experiment unless interaction is the explicit hypothesis.

### Stop conditions

- candidate meets accepted gates without new blockers;
- candidate is worse or complexity is unjustified and is reverted;
- experiment budget is exhausted;
- required corpus/model/environment/owner is unavailable;
- results are inconclusive and human/product decision is needed.

## 6. Operations Loop

### Inputs

- exact deployed artifact/configuration/environment;
- SLOs, alerts, owners, runbooks, dependency health, rollback/disable plan;
- incident or operational signal.

### Steps

```text
observe signal and correlate candidate
→ classify impact and contain
→ collect safe trace/audit/metrics
→ attribute failure to code, config, model, data, infra, dependency, security, or unknown
→ choose rollback/disable/repair/compensation
→ verify recovery and data integrity
→ add regression check and update runbook/ADR
→ review incident closure evidence
```

### Rules

- Unknown or partial external effects are contained and escalated; no blind retries.
- Security/privacy impact takes priority over availability optimization.
- Recovery success includes data/index/audit reconciliation, not only service health.
- Incident remediation is a new Work Order with its own acceptance and evidence.
- A rollback does not delete evidence of the failed candidate.

### Stop conditions

- service and data integrity are restored and verified;
- containment is stable but permanent fix requires a new slice;
- authority or dependency owner is missing;
- effect remains unknown and incident/human escalation owns the next action.

## 7. Review Loop

A review loop is not an endless panel.

```text
candidate + Evidence Package
→ impact-based reviewers
→ findings with severity/disposition
→ one bounded rework pass
→ evidence refresh
→ accept / hold / reject / defer
```

Full panel review is reserved for:

- cross-domain architecture changes;
- identity, trust boundary, ACL, audit, or Product Tool changes;
- pilot/release convergence;
- repeated failures suggesting system-level issues.

Low-impact nits that do not affect security, integrity, pilot outcome, evidence, operability, or user correctness go to backlog and do not keep the slice open.

## 8. Failure Attribution

Use one primary category and optional contributing categories:

- scope/requirement;
- architecture/contract;
- authorization/security;
- retrieval/index/data;
- generation/model/routing;
- citation/refusal/policy;
- API/persistence/migration;
- frontend/workflow;
- platform/dependency/network;
- evaluation/test defect;
- operations/process;
- unknown.

The next attempt must address the attributed cause or gather evidence to distinguish competing causes.

## 9. Human Escalation Packet

When escalation is required, provide:

- exact candidate/attempt and Work Order;
- problem and user/business impact;
- what was tried and evidence;
- current failure attribution and uncertainty;
- options including stop/defer/revert;
- security/data/operations consequences;
- recommended decision;
- decision deadline/trigger;
- safe state while awaiting the decision.

Do not ask a human to decide without preserving the evidence needed to decide.

## 10. Metrics for Harness Improvement

Observe, but do not optimize blindly:

- first-pass acceptance rate;
- repeated same-failure rate;
- average rework passes;
- escaped blocker/critical findings;
- evidence completeness defects;
- scope-expansion blocks;
- stale or missing ADR/traceability findings;
- time spent on low-impact nits;
- revert rate and reasons;
- false-positive/false-negative hook decisions;
- human escalation quality.

Harness changes require a falsifiable expectation and before/after evidence. More automation is not automatically better if it creates noise, hides authority, or weakens determinism.