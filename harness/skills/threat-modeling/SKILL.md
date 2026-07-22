# Threat Modeling Skill

## Trigger

Use for identity, ACL, data classification, new storage/model/network paths, logging/audit, Product Tool/MCP, external transfer, deployment zone, or security-control changes.

## Required Inputs

- exact candidate and Work Order;
- C4 and Trust Boundary register;
- data flows and classifications;
- Principal/roles/credentials;
- Tool/model/storage contracts;
- failure, audit, retention, and incident behavior.

## Steps

1. Identify assets, actors, owners, trust zones, entry points, and authoritative stores.
2. Trace data from source through validation, storage, retrieval/model/Tool use, response, logs, backup, and deletion.
3. Enumerate spoofing, tampering, repudiation/audit, disclosure, denial, privilege, prompt injection, confused deputy, stale ACL, replay, supply-chain, and partial-effect threats.
4. Rate severity using impact and exploitability; mark blockers explicitly.
5. Map preventive, detective, containment, recovery, and evidence controls.
6. Define fail-closed behavior and user-safe errors.
7. Define negative tests, leakage/redaction tests, disable/rollback, and incident owner.
8. Record residual risk and accountable acceptance requirements.

## Outputs

- threat/control matrix;
- blocker/critical findings;
- required contract/architecture changes;
- security test/eval plan;
- residual-risk and release recommendation.

## Checks

- Identity comes from a trusted server-side source.
- Authorization precedes relevance/model/Tool use.
- Vector/log/cache/backup copies follow source classification.
- Secrets never enter prompts, traces, repository, or user output.
- Development credentials cannot reach Product Runtime.
- Unknown side effects are not retried blindly.
- Required audit failure blocks success/effect acknowledgement.

## Escalation

Escalate blocker or unaccepted critical risk to accountable Security and business/domain owners with containment options and evidence.

## Stop Conditions

- required controls and tests are accepted;
- blocker requires HOLD/NO-GO;
- data/identity/owner information is missing;
- proposed change needs a new product scope or ADR.