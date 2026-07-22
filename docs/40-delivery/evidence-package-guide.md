# Agent Forge Evidence Package Guide

Status: Draft delivery baseline  
Owner: QA-Eval / Independent Release Governor  
Related: #108, #116

## 1. Purpose

An Evidence Package is the minimum structured record needed to support a claim that a bounded work slice, Build, release, or pilot stage is complete.

It prevents completion from meaning only “code or documents exist.” The package identifies the exact candidate, approved scope, requirements, decisions, changes, checks, evaluation, risk, limitations, reviewers, and final outcome.

The normative machine-readable structure is `harness/schemas/evidence-package.schema.json`.

## 2. Evidence Package Types

| Type | Use |
|---|---|
| `work_slice` | Documentation, architecture, harness, defect, or feature slice |
| `build` | Immutable Agent Build validation |
| `release_candidate` | Application/deployment release decision |
| `pilot_entry` | First real pilot GO/HOLD/NO-GO |
| `pilot_exit` | Pilot outcome and broader-rollout decision |
| `incident_remediation` | Security/reliability remediation and recurrence prevention |

## 3. Required Identity

Every package pins:

- package ID and schema version;
- package type and status;
- repository and candidate commit/PR where applicable;
- Agent/Agent Version/Build when applicable;
- environment;
- Work Order and issue references;
- requirement IDs and ADRs in scope;
- producer and accountable owners;
- creation/update time.

Evidence without an exact candidate identity is informative but cannot satisfy a release gate.

## 4. Required Sections

### 4.1 Scope

- problem and intended outcome;
- included and excluded work;
- changed files/components/configuration;
- affected users/data/trust boundaries;
- prohibited actions;
- acceptance criteria;
- deferred items.

### 4.2 Decisions

- linked Product Charter/Scope/Capability classification;
- adopted or proposed ADRs;
- alternatives and rationale for consequential choices;
- human approvals and conditions;
- unresolved decisions that cause HOLD.

### 4.3 Verification

Each verification record contains:

- check ID and type;
- command/workflow/eval reference;
- exact candidate/environment;
- status: passed, failed, incomplete, not_applicable;
- result summary and counts/metrics;
- artifact/log/report reference;
- executor and time;
- limitations and redaction statement.

### 4.4 Evaluation

- Eval Corpus/baseline version;
- model/index/policy/tool configuration;
- aggregate metrics;
- blocker cases;
- regression comparison;
- missing/unavailable cases;
- failure attribution;
- decision impact.

### 4.5 Security and Risk

- data classifications;
- trust boundaries crossed;
- identity/ACL impact;
- threat-model or security-review reference;
- blocker/critical/major findings;
- residual risks and accountable acceptance;
- secret/redaction review;
- rollback, disable, or containment plan.

### 4.6 Review

- required reviewer roles;
- independent reviewer where required;
- findings and disposition;
- unresolved comments;
- conflict-of-interest disclosure;
- GO/HOLD/NO-GO recommendation.

### 4.7 Limitations

Limitations are not hidden in prose. Each includes:

- description;
- impact and affected stage;
- owner;
- classification: code, decision, organization, data, model, infrastructure, security, operations;
- blocker status;
- resolution trigger or due condition;
- linked issue/ADR.

## 5. Evidence Quality Rules

| Rule | Meaning |
|---|---|
| Exactness | Evidence identifies exact commit/Build/config/corpus/environment |
| Reproducibility | Another authorized reviewer can repeat or inspect the check |
| Freshness | Evidence is valid for the candidate and has not been invalidated by later changes |
| Completeness | Mandatory gates and blocker cases are present; missing evidence is explicit |
| Independence | Release review is not only the implementer's assertion |
| Integrity | Artifacts/results have stable references or digests where useful |
| Minimization | Secrets and unauthorized classified content are not embedded in the package |
| Attribution | Failures are assigned to retrieval, generation, policy, model, data, infra, test, or unknown rather than hidden in averages |
| Honesty | `incomplete` is not converted to `passed`; technical evidence is not called pilot/production proof |

## 6. Package Status

| Status | Meaning |
|---|---|
| `draft` | Being assembled; not ready for decision |
| `evidence_ready` | Required sections assembled for review |
| `accepted` | Accepted for its declared stage and candidate |
| `hold` | Missing evidence/dependency/remediation prevents acceptance |
| `rejected` | Evidence or risk is unacceptable |
| `superseded` | Replaced by a later package; history retained |

## 7. Review Workflow

```text
Work Order accepted
→ candidate produced
→ producer assembles Evidence Package
→ required specialists review raw and summarized evidence
→ Release Governor checks identity, freshness, blockers, and independence
→ accountable decision records accepted / hold / rejected
→ package and decision linked to PR/release/pilot record
```

A package cannot self-accept.

## 8. Minimum Package by Change Type

### Documentation/architecture/harness policy

- exact branch/PR/commit and changed files;
- approved issue/slice;
- scope/non-goal conformance;
- syntax/schema/link verification;
- no-runtime-change confirmation;
- required CI status;
- architecture/security review where affected;
- limitations and next slice.

### Application change

- all of the above;
- Work Order and acceptance criteria;
- test-first or reproduction evidence;
- unit/integration/migration/E2E results;
- affected Eval Cases and regression report;
- trace/audit examples;
- security/data impact;
- rollout/rollback/disable plan.

### Pilot entry

- all Pilot Entry Gates;
- named owners/approvers;
- real corpus and identity evidence;
- internal model/storage/environment configuration;
- security/quality/performance results;
- backup/restore and ops exercises;
- open risks and HOLD conditions;
- signed GO/HOLD/NO-GO record.

## 9. Prohibited Evidence Practices

- claiming tests passed without a workflow/command result;
- reusing evidence from a different candidate without equivalence proof;
- deleting difficult Eval Cases to improve aggregate scores;
- presenting local/synthetic evidence as real-pilot proof;
- pasting secrets, tokens, confidential source text, or unrestricted model prompts;
- linking only a dashboard whose data can change without preserving a stable result reference;
- marking a non-code dependency complete because code is ready;
- allowing an implementer to be the sole release authority;
- ignoring failed or missing blocker cases;
- treating PR merge as proof of business or production readiness.

## 10. Example Outline

```yaml
schema_version: agentforge.evidence_package/v1
package_id: EP-2026-001
package_type: work_slice
status: evidence_ready
candidate:
  repository: storm-credit/agentforge
  commit_sha: <exact sha>
  pull_request: 123
scope:
  issue_refs: ["#122"]
  requirement_ids: ["DEL-001", "DEL-003"]
  included: ["Add Work Order schema"]
  excluded: ["Change application runtime"]
changes:
  files: ["harness/schemas/work-order.schema.json"]
verification:
  - check_id: CI-BACKEND
    type: ci
    status: passed
    reference: <workflow run>
risks:
  findings: []
limitations:
  - classification: implementation
    blocker: false
    description: Provider adapter not yet added
reviews:
  - role: release-governor
    outcome: accepted
final_decision:
  outcome: GO
  stage: merge
```

The example is illustrative and must validate against the current schema before use.