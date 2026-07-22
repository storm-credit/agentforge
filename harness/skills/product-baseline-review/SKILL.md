# Product Baseline Review Skill

## Trigger

Use when a proposal, issue, PR, or roadmap item may change product position, pilot scope, capability classification, readiness claims, or backlog admission.

## Required Inputs

- Product Charter
- Capability Map
- Scope and Non-Goals
- Product Glossary
- Current State
- proposal/change and affected requirement IDs

## Steps

1. State the user/business problem and intended measurable outcome.
2. Classify the capability as CURRENT-PROVEN, CURRENT-LIMITED, PILOT-REQUIRED, LATER-CANDIDATE, or NON-GOAL.
3. Verify whether current repository evidence supports the claimed readiness.
4. Compare included/excluded scope and backlog admission rules.
5. Identify affected users, owners, trust boundaries, data, operations, and release gates.
6. Separate code work from decision, organization, data, model, infrastructure, security, and operations dependencies.
7. Decide whether an ADR and accountable human scope decision are required.
8. Produce findings and an accept, changes-required, HOLD, or reject recommendation.

## Outputs

- scope-conformance result;
- capability classification and rationale;
- readiness-claim correction where needed;
- required owner/ADR/Work Order updates;
- explicit non-goals and deferred items.

## Checks

- Technical MVP is not called pilot or production ready.
- Later candidates are not presented as commitments.
- Delivery Harness features are not described as Product Runtime features.
- Specialists have not expanded scope.
- Every active backlog item has owner, requirements, acceptance, evidence, and reviews.

## Escalation

Escalate to PM Orchestrator and accountable human owner when product scope, pilot outcome, funding, organization, or risk acceptance must change.

## Stop Conditions

- proposal conforms and can enter a Work Order;
- proposal requires an explicit product decision;
- proposal remains a NON-GOAL or unsupported later candidate;
- evidence is insufficient to classify readiness.