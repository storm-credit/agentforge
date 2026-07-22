# Architecture Decision Review Skill

## Trigger

Use when a change affects component ownership, authoritative stores, state machines, trust boundaries, model/vector/object-store choices, deployment topology, or a consequential technical tradeoff.

## Required Inputs

- accepted product scope and Work Order;
- C4, Domain Model, State Machines;
- ADR Register and related ADRs;
- current implementation/deployment evidence;
- candidate options, constraints, and decision trigger.

## Steps

1. Verify the current physical and logical architecture; do not infer planned services are already deployed.
2. Identify affected domain entities, aggregates, authoritative stores, and owners.
3. Identify state transitions, concurrency, retry, audit, and retention effects.
4. Identify trust/data/identity/Tool/model boundaries.
5. Evaluate at least selected option, credible alternative, and do-nothing/defer.
6. Compare value, complexity, migration, security, operations, reversibility, and evaluation impact.
7. Determine whether a full ADR is required.
8. Record selected/recommended decision, consequences, controls, evidence, and follow-up.
9. Route impact-based review to Security, RAG/Data, Runtime/MCP, Platform, QA/Eval, or Product as applicable.

## Outputs

- ADR or decision-review result;
- updated architecture/domain/state references;
- migration/compatibility and rollback implications;
- required tests/eval/evidence;
- unresolved owner decisions and HOLD conditions.

## Checks

- Product scope is unchanged or separately approved.
- Logical and physical deployment claims are separated.
- Source-of-truth and derived stores are explicit.
- Invalid transitions and partial failure are handled.
- Development and Product Runtime boundaries do not collapse.
- Security and operations costs are not hidden.

## Escalation

Escalate to PM Orchestrator for scope conflict, Security for trust/ACL/data changes, and accountable platform/domain owner for environment or irreversible migration decisions.

## Stop Conditions

- decision and required controls are accepted;
- missing evidence prevents a responsible recommendation;
- product/security/organization authority is required;
- acceptable option does not exist within current scope.