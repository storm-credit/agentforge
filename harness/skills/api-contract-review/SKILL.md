# API Contract Review Skill

## Trigger

Use when adding or changing endpoints, request/response schemas, authentication, authorization, error/status semantics, pagination, idempotency, audit, versioning, or frontend/backend integration.

## Required Inputs

- Work Order and requirement IDs;
- Domain Model and State Machines;
- trust/security requirements;
- current API implementation/schema and consumers;
- migration/compatibility plan;
- test and evidence plan.

## Steps

1. Identify resource, aggregate owner, action, Principal, and state transition.
2. Verify authorization and data-classification rules before handler/business behavior.
3. Review request schema, normalization, limits, unknown fields, and idempotency.
4. Review response schema, redaction, pagination, stable IDs, and version references.
5. Define safe errors for denial, refusal, validation, conflict/stale state, rate/timeout, dependency, and internal failure.
6. Check concurrency, optimistic locking, retry safety, and partial failure.
7. Check Audit Events and runtime trace fields.
8. Check backward compatibility, deprecation, and consumer impact.
9. Define unit/integration/E2E and negative security tests.

## Outputs

- structured Review Result;
- accepted or required contract changes;
- compatibility/migration actions;
- authorization, audit, idempotency, and test requirements.

## Checks

- Client-supplied identity is not trusted.
- Endpoint cannot bypass aggregate/state guards.
- Unknown fields/targets do not become model/Tool authority.
- Error responses do not leak resource existence, secrets, stack traces, or forbidden content.
- Published immutable resources are not edited in place.
- Mutations have concurrency and audit behavior.
- Frontend cannot infer success from ambiguous status.

## Escalation

Escalate domain/state change to Product Architect, identity/data risk to Security, and breaking consumer/migration decision to PM and affected owners.

## Stop Conditions

- contract and tests are accepted;
- architecture/requirement decision is missing;
- security blocker exists;
- compatibility or migration risk cannot be resolved within scope.