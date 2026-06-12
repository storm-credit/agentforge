# AgentForge Local Live Verification

Date: 2026-06-12
Branch: `feat/binary-upload`
Slice: PDF/DOCX document upload ingest

## Decisions Remembered

- `agentmemory` MCP was not available in the current Codex tool set; this file is the local handoff substitute.
- Scope stayed YAGNI: PDF and DOCX server-side text extraction only. No MinIO/raw file retention, no XLSX, no OCR, no async ingestion.
- Multipart endpoint: `POST /api/v1/knowledge/documents/upload`.
- Upload response: `{ document, index_job }`.
- Raw byte checksum is stored on `documents.checksum`.
- `object_uri` uses `upload://<filename>` until object storage is introduced.
- PDF/DOCX extraction feeds the existing text chunker, embedding, Qdrant, and ACL payload path.

## Verification Results

- Backend targeted contracts: `10 passed`
  - `tests/test_parser_contracts.py`
  - PDF upload contract
  - DOCX upload contract
  - unsupported upload MIME contract
- Backend full suite with `apps/api/.env` temporarily moved aside: `77 passed`
- API ruff: `All checks passed!`
- Web TypeScript: `node node_modules/typescript/bin/tsc --noEmit` passed
- Web Playwright render: `tests/knowledge-upload.spec.ts` passed against `http://127.0.0.1:3300`
- Eval harness: `15 passed`

## Live Verification

Local stack:

- Docker containers started: `agentforge-ollama`, `compose-postgres-1`, `compose-qdrant-1`
- API health: `/healthz` ok, `/readyz` database ok

Live uploaded source:

- `source_id`: `14e0c70f-5a15-4ce1-8cdb-aabc37a6c667`
- PDF document: `c6e66d5a-8090-40e9-baf7-6841cde66692`
  - job status: `succeeded`
  - chunks: `1`
- DOCX document: `de33bcdf-30f9-487b-9c75-4464e4514887`
  - job status: `succeeded`
  - chunks: `2`
- Agent: `ca64b5b3-62f6-4324-813f-34a0a7935322`
- Run status: `succeeded`
- Grounded answer verified: PDF allowance answer returned from uploaded PDF policy.
- Citations included the uploaded PDF and DOCX documents.
- Guardrail snapshot:
  - `acl_filter_applied`: true
  - `citation_required`: true
  - `citation_validation_pass`: true
  - `security_finalcheck_pass`: true

## Follow-Up

- Add raw file storage through MinIO or S3-compatible object storage.
- Add structured citation locators for PDF pages and DOCX heading/paragraph/table positions.
- Add XLSX ingestion as a separate parser slice.
- Add OCR/quarantine handling for scanned PDFs.
