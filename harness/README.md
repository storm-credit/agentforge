# Agent Forge Delivery Harness

Status: Foundation  
Owner: PM Orchestrator  
Related Epic: #108

## Purpose

The `harness/` directory contains the version-managed, vendor-neutral operating contracts used to plan, implement, review, and verify Agent Forge.

It exists so that critical delivery behavior is not hidden only inside a local Claude configuration, chat session, personal memory store, or a single model provider.

The harness governs **how Agent Forge is built**. It is separate from the **Agent Forge product runtime**, which governs how published end-user agents execute.

## Boundary

| Harness concern | Product runtime concern |
|---|---|
| PM and specialist work assignment | Published agent execution |
| Repository code/document tools | Registered enterprise tools |
| Development GitHub/MCP access | Product MCP/Tool Pack access |
| Design, build, review, and eval loops | Retrieve, generate, validate, respond, audit |
| Branch/PR/test evidence | Run trace, retrieval evidence, policy decisions |

A development tool does not become a product tool automatically. Product tools require a separate registry, risk assessment, permission policy, and audit contract.

## Planned Layout

```text
harness/
  manifest.yaml
  agents/
  skills/
  hooks/
  mcp/
  policies/
  schemas/
```

### `agents/`

Role contracts for the PM Orchestrator and specialists. Each contract will define:

- mission and authority;
- inputs and required context;
- owned artifacts;
- prohibited decisions;
- acceptance criteria;
- handoff and escalation rules;
- recommended model class where material.

### `skills/`

Reusable, reviewable procedures such as:

- product and architecture review;
- threat modeling;
- RAG evaluation design;
- API contract review;
- migration verification;
- release governance.

A skill is a repeatable procedure, not an unrestricted persona prompt.

### `hooks/`

Deterministic guardrails around supported agent-assisted development environments.

The initial policy targets these lifecycle points:

- SessionStart: load current state, approved scope, ADRs, and test baseline.
- PreToolUse: block destructive commands, protected files, direct main changes, and unregistered tools.
- PostToolUse: run formatting, lint, targeted tests, and change-impact checks.
- SubagentStop: require completion evidence, risks, and scope-conformance checks.
- Stop: require decision/evidence updates and verify loop termination.

Provider-specific hook configuration may live outside this directory, but the policy source must remain versioned here.

### `mcp/`

Contracts for MCP usage, separated into:

1. development MCP servers and tools;
2. product runtime MCP servers and tools.

Every registered tool should eventually include:

- stable tool and server identifiers;
- owner and purpose;
- input/output classification;
- side-effect and risk level;
- allowed roles and agents;
- approval requirements;
- schema/version hash;
- timeout and retry policy;
- audit and redaction policy;
- fail-open/fail-closed behavior;
- rollback or compensation requirements for writes.

### `policies/`

Cross-agent rules including:

- model routing;
- release and coding gates;
- loop budgets;
- human escalation;
- completion-claim discipline;
- protected resource policy.

### `schemas/`

Machine-readable contracts for:

- agent definitions;
- work orders;
- review results;
- evidence packages;
- tool contracts;
- decision records.

## Engineering Loops

### Design Loop

```text
Problem
→ constraints and evidence
→ alternatives
→ risk/trade-off review
→ decision record
→ contract and acceptance criteria
→ design approval
```

No implementation starts while a material architecture, permission, data, or evaluation decision remains undefined.

### Build Loop

```text
Approved work order
→ failing test or explicit acceptance check
→ minimal implementation
→ targeted and regression tests
→ specialist review
→ evidence package
→ orchestrator merge decision
```

### Eval Loop

```text
Baseline
→ one controlled change
→ deterministic and model-based evaluation where appropriate
→ regression comparison
→ adopt, revise, or revert
```

Authorization and leakage gates must remain deterministic. LLM-as-judge cannot be the sole release authority for those gates.

### Operations Loop

```text
Deploy
→ observe traces and service health
→ classify failure
→ assign accountable owner
→ recover or roll back
→ update evidence and decision records
```

## Loop Budgets

Default limits for future machine-readable policy:

- specialist self-review: maximum 2 passes;
- implementation rework after formal review: maximum 1 pass before escalation;
- repeated same failure: escalate after 2 occurrences;
- full expert panel: only for cross-domain changes or scheduled convergence reviews;
- low-impact findings without pilot/security/integrity/evidence impact: backlog rather than immediate iteration;
- no automatic creation of work merely to avoid declaring a stable stopping point.

## Human Escalation

Human decision is required when:

- product scope changes;
- a write or external-transfer tool is introduced;
- security specialists disagree on a trust boundary;
- an evaluation improvement trades off leakage, citation, or refusal safety;
- a model-generated fix fails twice;
- real pilot ownership, SSO, document access, or deployment infrastructure is required;
- a completion claim lacks reproducible evidence.

## Evidence Package

Each implementation slice will eventually produce a structured package containing:

- work-order ID and scope;
- affected requirement and ADR references;
- changed files;
- tests and commands executed;
- before/after evaluation where relevant;
- security and data review outcomes;
- known limitations;
- rollback or revert path;
- reviewer and orchestrator decision.

## Current Foundation

This first slice adds only:

- this operating guide;
- `manifest.yaml` as the initial inventory and policy skeleton;
- product and current-state baselines under `docs/`.

It does not add runtime agents, MCP integrations, hooks, or application behavior yet.
