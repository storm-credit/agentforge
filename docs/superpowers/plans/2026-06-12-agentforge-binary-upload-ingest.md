# AgentForge Binary Upload Ingest Plan

Date: 2026-06-12
Branch: `feat/binary-upload`
Status: implemented locally, pending full/live verification

## Brainstorming Decisions

- Formats in scope: PDF and DOCX. TXT/MD behavior stays supported. XLSX remains out of scope.
- Raw object storage is out of scope for this slice. The upload route records `upload://<filename>` and indexes extracted text immediately.
- API shape: add `POST /api/v1/knowledge/documents/upload` as a multipart sibling instead of changing the existing JSON register/index routes.
- Parser shape: `extract_text(mime_type, file_bytes) -> str` / `extract_text_from_bytes(...)` handles PDF/DOCX/TXT/MD extraction, then the existing text chunker is reused.
- Downstream indexing is unchanged: parse/chunk -> embedding model -> vector store/Qdrant payload with ACL metadata.

## Implementation Checklist

- [x] Add `pypdf`, `python-docx`, and `python-multipart` dependencies.
- [x] Add PDF/DOCX text extraction contracts.
- [x] Add multipart upload contract tests for PDF and DOCX indexing success.
- [x] Add unsupported upload MIME rejection test.
- [x] Wire `run_index_job` to extract binary MIME types before text chunking.
- [x] Add `/knowledge/documents/upload` endpoint returning `{document, index_job}`.
- [x] Update `/knowledge` UI to accept `.txt,.md,.pdf,.docx`.
- [x] Preserve TXT/MD paste/register/index behavior.

## Security Review Notes

- Upload size is capped by `MAX_EXTRACT_BYTES` before indexing.
- PDF page count is capped by `MAX_PDF_PAGES`.
- Unsupported MIME types return HTTP 415 before document registration.
- Oversized uploads return HTTP 413 before document registration.
- Extraction failures, encrypted PDFs, empty extraction, or non-indexable ACL metadata become failed index jobs.
- The upload checksum is calculated from raw bytes, not extracted text.
- Extracted content is stored only as normal indexed chunks; raw file storage is intentionally deferred.

## Verification Targets

- Targeted backend: parser contracts and multipart upload contracts.
- Full backend suite with `apps/api/.env` temporarily moved aside.
- Web typecheck with direct `node` TypeScript CLI.
- Playwright render check for `/knowledge` upload accept list.
- Live: PDF and DOCX upload -> index succeeded -> connect source in builder -> grounded answer.

## Known Deferrals

- MinIO/object storage raw file retention.
- Rich PDF page/block and DOCX paragraph/table structured citation fields.
- OCR for scanned PDFs.
- XLSX ingestion.
