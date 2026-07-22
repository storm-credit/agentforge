# Migration Verification Skill

## Trigger

Use for database schema/data migrations, index/vector generation changes, object layout changes, configuration format changes, or irreversible data lifecycle operations.

## Required Inputs

- accepted Work Order and ADR where required;
- source and target schema/state;
- authoritative store and dependent derived stores;
- data volume/classification and concurrency constraints;
- rollback or forward-fix strategy;
- backup/restore and reconciliation plan.

## Steps

1. Verify the exact current schema/state and candidate migration chain.
2. Identify affected aggregates, constraints, indexes, ACL/audit data, and consumers.
3. Classify change as additive, backfill, contract/breaking, destructive, or cross-store.
4. Define forward migration, compatibility window, application ordering, and rollback/forward-fix.
5. Define idempotency, restart/resume, transaction boundaries, locks, and failure checkpoints.
6. Define reconciliation counts/checksums and derived-store invalidation/rebuild.
7. Test upgrade from supported prior state and downgrade when supported; otherwise test forward-fix/restore.
8. Exercise concurrent reads/writes or explicitly justify maintenance-mode behavior.
9. Verify audit, retention, deleted/revoked data, and secret/classification handling.
10. Record commands, timings, artifacts, limitations, and operational runbook.

## Outputs

- migration review/result;
- deployment ordering and compatibility statement;
- test and reconciliation evidence;
- rollback/restore/forward-fix plan;
- HOLD conditions and required owners.

## Checks

- No data loss or authorization weakening is hidden by successful process exit.
- Vector/object/cache derived state reconciles with authoritative metadata.
- Partial execution can resume or be contained safely.
- Destructive cleanup is separated from reversible rollout where practical.
- Published Builds and audit history retain valid references.
- Backup existence is not treated as restore proof.
- Production execution requires explicit authority and target evidence.

## Escalation

Escalate irreversible loss/retention decisions to accountable data/security owners, production timing/rollback to Platform/Service Owner, and aggregate changes to Product Architect.

## Stop Conditions

- migration and reconciliation evidence pass;
- rollback/forward-fix/restore is unacceptable or untested;
- target environment/backup/authority is missing;
- data integrity or security blocker remains.