# Sprint 1 Real Ingestion Runbook

This runbook verifies the first real document ingestion path for Agent Forge.

## Goal

Prove that an operator can upload a TXT/Markdown file, store the raw object, index it without synthetic `source_text`, retrieve an ACL-filtered citation, and create a runtime trace from the same uploaded document.

This is also the current API-backed eval evidence path. The dedicated `/api/v1/eval/runs` worker is still a planned product endpoint; until it lands, the script below seeds the synthetic corpus through the public APIs and exercises runtime trace storage end to end.

## Local Stack

From the repository root:

```powershell
./tools/smoke/compose-smoke.ps1 -Boot -WebPort 0
```

The dev compose stack configures the API to use MinIO through the S3-compatible storage adapter:

- backend: `AGENT_FORGE_OBJECT_STORAGE_BACKEND=minio`
- endpoint: `http://minio:9000`
- bucket: `agent-forge-documents`

## Smoke Check

After the API is available:

```powershell
./tools/smoke/real-ingestion-smoke.ps1 -ApiBaseUrl "http://127.0.0.1:8000/api/v1"
```

For a single eval-oriented command that also checks the synthetic corpus, deterministic scorer, real upload smoke, and full 30-case API runner:

```powershell
./tools/smoke/api-eval-runner-smoke.ps1 -ApiBaseUrl "http://127.0.0.1:8000/api/v1"
```

To boot the compose stack and then run the eval smoke:

```powershell
./tools/smoke/api-eval-runner-smoke.ps1 -BootStack -WebPort 0
```

The wrapper stops the compose stack after the run unless `-KeepStack` is passed.

The script checks:

- `POST /api/v1/knowledge/documents/upload` stores a raw Markdown file.
- The returned document has `object_uri`, `sha256-*` checksum, MIME type, and ACL groups.
- `POST /api/v1/knowledge/documents/{document_id}/index-jobs` succeeds without `source_text`.
- Chunk metadata returns citation locators while hiding raw chunk content.
- `POST /api/v1/knowledge/retrieval/preview` returns the uploaded chunk.
- A published agent version can run through `POST /api/v1/runs`.
- Runtime steps and retrieval hits are stored for trace review.
- `python eval/harness/run_api_synthetic_eval.py` uploads the 10 synthetic corpus documents, indexes them from object storage, runs all 30 cases, and compares `answer`, `policy_denied`, `no_context`, and `refuse` outcomes.

## Runtime Trace Evidence

The API-backed smoke creates one published agent and one runtime run against the uploaded document. The run must finish with:

- `status=succeeded`
- one citation from the uploaded document
- `guardrail.acl_filter_applied=true`
- `guardrail.citation_validation_pass=true`
- five ordered runtime steps: `guard_input`, `retriever`, `generator`, `citation_validator`, `guard_output`
- one stored retrieval hit with the uploaded chunk ID

Trace review endpoints:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/runs/<run-id>/steps"
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/runs/<run-id>/retrieval-hits"
```

Expected audit events along the path include `knowledge_source.created`, `document.uploaded`, `document.indexed`, `retrieval.previewed`, `agent.created`, `agent_version.created`, `agent_version.published`, and `run.created`.

## API Notes

Upload uses the raw request body, not multipart form data. Required metadata is passed as query parameters and the original file name is passed in `X-Agent-Forge-Filename`.

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/api/v1/knowledge/documents/upload?knowledge_source_id=<source-id>&title=Remote%20Work&access_groups=all-employees" `
  -Headers @{ "X-Agent-Forge-Filename" = "remote-work.md" } `
  -ContentType "text/markdown" `
  -InFile ".\remote-work.md"
```

Indexing fails closed when the uploaded object is missing, not UTF-8, unsupported by the TXT/MD parser, or missing ACL metadata.
