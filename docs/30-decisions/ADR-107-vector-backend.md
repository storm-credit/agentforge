# ADR-107: Vector backend for closed-network staging

Status: Adopted (backend selection and ACL-in-query contract only — see Consequences for what remains open)
Date: 2026-08-22
Owners: Platform / RAG-Data
Related requirements/issues/PRs: PR #59 (readyz vector/object-store checks); ADR-008 (`ADOPTED`, "Vector DB is a derived search index, not the authority for document ACL or ownership"); ADR-003 (`ADOPTED`, authorization before relevance); ADR-011 (`ADOPTED`, reranking receives only already-authorized chunks); ADR-109 (closed-network staging topology, `OPEN`); ADR-111 (backup/restore/RTO/RPO, `OPEN`)
Supersedes / Superseded by: None

## Context

`docs/30-decisions/adr-register.md` §4 lists ADR-107 ("Vector backend for closed-network staging") as `OPEN`, framed as a choice between Qdrant and pgvector, with evidence required on the ACL query contract, backup/restore, capacity, operations skill, and offline packaging. Separately, ADR-008 already records — `ADOPTED` — that the vector store is a derived search index and never the authority for ACL or ownership.

In practice, the repository has already built and runs exactly one vector-backend implementation: Qdrant, via `apps/api/app/infra/qdrant_store.py`. There is no pgvector adapter anywhere in the tree, and no runtime switch that selects between vector-database technologies — only `AGENT_FORGE_QDRANT_URL`, which points the existing Qdrant client at a different endpoint. This ADR records that already-effective implementation choice. It does not, and cannot, close the operational sub-decisions (backup/restore, capacity, offline packaging) that ADR-107's evidence-required column also names — those remain owned by ADR-109 and ADR-111 and are not settled by anything below.

Verified against the repository (2026-08-22):

- `apps/api/app/infra/qdrant_store.py` implements `QdrantVectorStore.search()`, which builds the ACL filter via `build_qdrant_acl_filter(acl_filter, ...)` (itself built from `build_acl_filter(principal)` in `apps/api/app/domain/vector.py:160`) and passes it as `query_filter` into the same `query_points(...)` call that performs the similarity search — the authorization filter is evaluated by Qdrant as part of the query, not applied only after scores are computed. A second, redundant `payload_allows(payload, acl_filter)` check runs in application code on the returned hits as defense-in-depth, and any hit that fails it is dropped and logged as a warning rather than trusted.
- The collection name is `chunks_active` (`apps/api/app/domain/vector.py:26`, `apps/api/app/infra/qdrant_store.py:97`).
- `/readyz` (`apps/api/app/main.py`) reports a `vector_store` field (`ok` / `unavailable` / `skipped`) via `check_vector_store()`, and degrades the endpoint's HTTP status when it fails.
- `AGENT_FORGE_QDRANT_URL` (`apps/api/app/core/config.py`, `qdrant_url: str = "http://localhost:6333"`) is the only setting that changes between the current local/dev deployment and a closed-network target, per `docs/40-delivery/in-house-dry-run.md`.
- A `FakeVectorStore` also exists (`apps/api/app/domain/vector.py`). It is used by the hermetic test suite, but it is also invoked at runtime as a fallback in `apps/api/app/api/v1/knowledge.py` and `apps/api/app/api/v1/runs.py` when a live Qdrant query raises an exception, so that retrieval preview / run execution degrade gracefully instead of hard-failing. It holds no persisted vectors and is not a second production backend option — it does not change the "one real backend" conclusion above.

## Decision Drivers

- Authorization must be enforced in the retrieval query itself, before relevance narrows the candidate set (ADR-003), not as a post-hoc filter on already-ranked results.
- Migration to the closed network must not require rewriting the vector-store adapter — only reconfiguring an endpoint.
- The hermetic test suite and any degraded/offline runtime path must not require a live vector database.

## Options Considered

### Option A — Qdrant (current, implemented)

Real ACL-in-query filtering already exists and is tested; a working `/readyz` health check exists; the collection contract (`chunks_active`) is stable and has automated coverage. Cost: nothing further to build to reach a closed-network Qdrant endpoint, but Qdrant-specific backup/restore, capacity planning for the pilot corpus, and closed-network offline packaging (container image, license terms, install runbook) are not evidenced anywhere in this repository.

### Option B — pgvector

Would reuse the already-`ADOPTED` PostgreSQL store (ADR-007) and its existing operational posture (backup, access control, monitoring), at the cost of writing a new adapter, a new ACL-filter contract equivalent to `build_qdrant_acl_filter`, and migrating `chunks_active`. No code for this option exists in the repository; it would be new work, not a configuration change.

### Do nothing / defer

Not viable as a pilot-blocking decision: the technical MVP already depends on a working vector backend today. "Defer" would mean discarding the ACL-aware retrieval path that ADR-003 and ADR-011 already depend on.

## Decision

Qdrant remains the vector backend, exactly as implemented, with ACL enforcement in-query via `build_acl_filter`/`build_qdrant_acl_filter`. Migration to a closed-network environment is expected to be a configuration change (`AGENT_FORGE_QDRANT_URL`) rather than a re-architecture. This decision covers backend selection and the ACL-in-query contract only.

## Consequences

Positive: no adapter work is required to reach the closed network; the ACL invariant (ADR-003) is enforced at the query layer rather than relying solely on a post-filter.

Negative / explicitly open: backup/restore procedure, RTO/RPO, capacity sizing against the accepted pilot corpus (ADR-102), and a closed-network offline package (image, license, install runbook) for Qdrant are **not evidenced by anything in this repository** and are not resolved by this ADR. They remain owned by ADR-109 (closed-network staging topology) and ADR-111 (backup/restore, RTO/RPO). This ADR must not be read as closing either.

## Required Controls and Evidence

- The Qdrant-backed test suite (including `apps/api/tests/test_vector_store_factory.py`) continues to pass in CI.
- `/readyz`'s `vector_store` field must report `ok` before any environment is declared ready for use.
- Before ADR-109/ADR-111 can close, a Qdrant backup/restore drill and a capacity estimate against the accepted pilot corpus (ADR-102) must exist. Neither exists today; this ADR does not create them.

## Follow-up

- Platform / RAG-Data: produce a Qdrant backup/restore runbook and a capacity estimate once ADR-102 (pilot document inventory) is decided, and record them under ADR-109/ADR-111 — not as an amendment to this ADR.
