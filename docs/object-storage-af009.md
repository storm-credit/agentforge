# Object Storage Wiring (AF-009, slice 3/4)

Persists original upload bytes to an object store so the index worker can fetch content
from storage instead of requiring it inline on the request. Opt-in; default off (no
behavior change).

## What it does
- `app/infra/object_store.py`: `ObjectStore` protocol + `InMemoryObjectStore` (tests/local)
  + lazy `MinioObjectStore` (S3-compatible) + `get_object_store()` factory.
- Storage key = `documents/{document_id}/source` (`document_object_key`) — derived from the
  server UUID, **never** from the user filename/`object_uri` → no path-traversal surface.
- `knowledge.py`:
  - Upload route puts the original bytes to the store (when enabled).
  - `process_index_job` fetches bytes from the store when no inline `source_text` is given,
    then indexes — resolving the previous `SOURCE_CONTENT_UNAVAILABLE` fail-closed gap.
- Config gate `AGENT_FORGE_OBJECT_STORE_BACKEND` = `none` (default) | `memory` | `minio`
  (+ endpoint/access_key/secret_key/bucket/secure). `none` keeps the prior inline-only behavior.

## Scope (YAGNI)
- The fetch-from-storage path is wired; a full async queue/worker split is **out of scope**
  (deferred) — `process_index_job` remains the worker entrypoint.
- Indexing still passes through the existing `document_can_be_indexed` ACL/confidentiality
  gate; object storage only supplies raw bytes.

## Verification (2026-06-15)
- Unit (`test_object_store.py`): put/get round-trip, exists, missing→`ObjectNotFound`, key traversal-safe.
- Contract (`test_metadata_contracts.py`): with `memory` backend, a queued job with **no inline
  content** fetches from the store → **succeeded** (≥1 chunk); with default `none` backend the
  same job still **fails closed** with `SOURCE_CONTENT_UNAVAILABLE`.
- Full suite (.env aside): **110 passed, 0 skipped**. ruff clean.
- `security-review`: **no high-confidence findings** (key from UUID, no ACL bypass, env-only creds).
- **Live (real MinIO, `compose-minio-1` on :9000, backend=minio):**
  - `MinioObjectStore` put/get/exists/not-found round-trip OK.
  - End-to-end API: upload a `.txt` → stored in MinIO → fresh queued index-job with **no
    source_text** → process → **succeeded, 1 chunk** (fetched from MinIO). Deterministic round-trip.

## Limits (honest)
- Async ingest is just the fetch path, not a real queue/worker separation.
- Live test used the dev MinIO container + dev creds; bucket lifecycle/retention/large-file
  streaming not exercised. Default backend stays `none` until deployment wires real MinIO.
