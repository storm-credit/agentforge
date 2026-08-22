# ADR-108: Object storage implementation

Status: Provisional (matches the existing status of ADR-009, which this ADR narrows for the closed-network pilot; the on/off choice itself is a separate, still-open decision — see Consequences)
Date: 2026-08-22
Owners: Platform
Related requirements/issues/PRs: PR #30 (AF-009 object storage), `docs/object-storage-af009.md`; ADR-009 (`PROVISIONAL`, "Raw documents/artifacts use an object-store abstraction; metadata/checksum lineage remains in the domain store"); ADR-102 (pilot document inventory, owners, classification, ACL, and retention, `OPEN`); ADR-110 (audit retention/access/redaction/sink, `OPEN`)
Supersedes / Superseded by: None

## Context

`docs/30-decisions/adr-register.md` §4 lists ADR-108 ("Object storage implementation") as `OPEN`, framed as a choice between MinIO-compatible, an approved internal object store, or filesystem-with-controls, with evidence required on access, checksum, backup/restore, retention, and HA. ADR-009 already records, `PROVISIONAL`, that raw documents use an object-store abstraction distinct from the domain store.

Verified against the repository (2026-08-22):

- `apps/api/app/core/config.py` defines `object_store_backend: Literal["none", "memory", "minio"] = "none"`, plus `object_store_endpoint`, `object_store_access_key`, `object_store_secret_key`, `object_store_bucket`, and `object_store_secure`. The default is `none` — no bytes are persisted anywhere by default.
- `apps/api/app/infra/object_store.py` defines an `ObjectStore` protocol with exactly three operations: `put`, `get`, `exists`. **There is no `delete` operation on the protocol or on either concrete implementation** (`InMemoryObjectStore`, `MinioObjectStore`).
- Upload persists the original bytes when a backend is configured: `apps/api/app/api/v1/knowledge.py:631-633` calls `object_store.put(document_object_key(document.id), raw)` right after the `Document` row is created.
- The queued index-job processing path fetches the bytes back when the caller did not supply `source_text` inline: `apps/api/app/api/v1/knowledge.py:841` calls `_fetch_object_bytes(document)` (defined at line 1081), which returns `None` if the store is unset (`backend="none"`) or the key is missing, in which case the job fails with no source content rather than silently succeeding.
- `apps/api/tests/test_object_store.py` covers put/get round-trip, `exists`, the `ObjectNotFound` error path, and that `document_object_key` is traversal-safe (a fixed count is not stated here because it will go stale; see the file directly).
- `deploy/compose/docker-compose.dev.yaml` wires a `minio` service for local development.
- `docs/object-storage-af009.md` documents the design.
- **No code path anywhere calls a delete/remove on the object store.** `DELETE /documents/{document_id}` (`apps/api/app/api/v1/knowledge.py:245`, `archive_document`) sets `document.status = "archived"` and marks chunks archived, but does not touch object storage at all — even if a backend is enabled and the original bytes were persisted at upload, archiving (soft-delete) a document does not remove them, and the `ObjectStore` protocol offers no method that could do so today.

## Decision Drivers

- Re-indexing a document must not require the caller to re-upload it.
- The abstraction must be genuinely optional so environments that decide against original-document retention pay no cost.
- Original bytes are metadata-adjacent artifacts, not the ACL/ownership authority (consistent with ADR-009 and ADR-008's parallel treatment of the vector store).

## Options Considered

### Option A — MinIO-compatible object store (current, implemented)

Already wired end-to-end (write on upload, read on re-index), opt-in via a single `Literal` setting, with a working dev-compose service and a documented design. Cost: no delete capability exists, so enabling retention today has no matching deletion mechanism.

### Option B — Approved internal object store

Would require a new `ObjectStore` implementation behind the same protocol; the protocol itself (put/get/exists, no delete) would need to grow a delete method regardless of which backend is chosen, if retention/deletion policy requires it. No code for an alternative backend exists.

### Do nothing / defer

Viable as a pilot choice (`backend="none"`) and is in fact the current default — but "do nothing" is itself a retention decision (original documents are never retained), not an absence of one, and must be made explicitly rather than inherited silently from a default.

## Decision

The MinIO-compatible object-store abstraction, as implemented, is the recorded technical approach for original-document retention when a pilot chooses to enable it. The default remains `none` (off). This ADR does not decide whether the pilot turns it on.

## Consequences

Positive: turning retention on requires only a configuration change (`AGENT_FORGE_OBJECT_STORE_BACKEND=minio` plus endpoint/credentials/bucket) and existing code already reads from and writes to it correctly.

Negative / explicitly open:
- **"Default off" is not a neutral technical fact — it is the pilot's retention decision until someone chooses otherwise.** Turning it on is a real, separate decision that belongs to ADR-102 (pilot document inventory, classification, and retention), because it determines whether original uploaded bytes exist at all outside the vector index.
- **If retention is turned on, there is currently no way to delete retained bytes.** Archiving a document (the existing soft-delete/ACL-revocation path) purges it from Qdrant search but leaves any persisted original bytes in the object store indefinitely, and the `ObjectStore` protocol has no delete method to remove them even if a caller wanted to. This is a genuine gap between "revoke access to a document" and "the document's original bytes still exist," and it must be closed (protocol + call site) before a pilot enables retention under any deletion or right-to-be-forgotten obligation. This interacts with ADR-102 (retention/deletion rules) and with the general audit/compliance posture referenced by ADR-110.
- Backup/restore and HA for whichever object-store backend is chosen are not evidenced in this repository and remain open under ADR-109/ADR-111, in the same way as for the vector backend (ADR-107).

## Required Controls and Evidence

- `apps/api/tests/test_object_store.py` continues to pass in CI.
- `/readyz`'s `object_store` field (`apps/api/app/main.py`, via `check_object_store()`) must report `ok` whenever a backend is configured.
- Before a pilot may enable `object_store_backend != "none"`, a delete/removal capability must be added to the `ObjectStore` protocol and wired to the archive (and, if applicable, hard-delete) path — this does not exist today and is a prerequisite, not an assumption.

## Follow-up

- Platform: add a `delete` operation to the `ObjectStore` protocol and both implementations, and call it from the archive path, before any pilot corpus with retention/deletion obligations enables the MinIO backend.
- Product/Security (ADR-102): decide, per pilot document inventory, whether original-document retention is required at all, and if so under what deletion policy.
