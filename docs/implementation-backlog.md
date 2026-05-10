# Implementation Backlog

This backlog translates the Agent Forge MVP design into development-ready epics and stories. The MVP remains limited to an internal document-based RAG Agent Builder.

## 1. Epics

| Epic | Name | Goal | Priority |
|---|---|---|---|
| EP-00 | Development foundation | API, web, DB, and compose skeleton | P0 |
| EP-01 | Agent Registry | Agent Card and version/publish lifecycle | P0 |
| EP-02 | Knowledge ingestion | Document upload, storage, and indexing jobs | P0 |
| EP-03 | ACL retrieval | Permission-aware retrieval and citation candidates | P0 |
| EP-04 | Runtime run | Question, retrieval, answer, and trace logging | P0 |
| EP-05 | Agent Studio | Admin creation, document, test, and trace screens | P1 |
| EP-06 | Audit and eval | Audit events, golden set, release gates | P1 |
| EP-07 | Closed-net operations | Offline deployment, backup, observability | P1 |

## 2. P0 Stories

| ID | Story | Done when |
|---|---|---|
| AF-001 | Create FastAPI skeleton | `/healthz`, `/readyz`, and OpenAPI are available |
| AF-002 | Create Next.js shell | `/agents`, `/knowledge`, `/eval`, and `/audit` routes exist |
| AF-003 | Add PostgreSQL migration base | Fresh DB migration succeeds |
| AF-004 | Add dev compose stack | API, web, DB, object storage, and vector store can boot locally |
| AF-005 | Add Agent and Version tables | Agent metadata and draft version can be saved |
| AF-006 | Implement Agent CRUD API | List, create, update, and detail contract tests pass |
| AF-007 | Implement version validate/publish | Only one published version exists per agent |
| AF-008 | Add Knowledge Source and Document tables | Document metadata and ACL metadata can be saved |
| AF-009 | Implement MinIO upload | Raw file, checksum, and audit event are saved |
| AF-010 | Implement index job skeleton | Queued, running, succeeded, failed states are recorded |
| AF-011 | Add TXT/MD parser smoke path | Synthetic documents produce chunks |
| AF-012 | Add vector adapter interface | Fake adapter contract tests can run |
| AF-013 | Add ACL filter model | Allowed and blocked test users produce different candidates |
| AF-014 | Add retrieval preview API | Unauthorized documents never appear in retrieval results |
| AF-015 | Add runtime run API skeleton | Run and run-step rows are stored |
| AF-016 | Add citation validator | Citation-required responses can fail validation |
| AF-017 | Add audit event writer | Publish, upload, and run events are recorded |
| AF-018 | Add synthetic corpus v0.1 | 30 ACL/citation test questions exist |
| AF-019 | Add Sprint 0 API contract tests | Metadata APIs have request/response tests |
| AF-020 | Add synthetic corpus schema | ACL/citation cases have machine-readable expected results |
| AF-021 | Add compose boot smoke | Fresh stack boot and health checks are repeatable |
| AF-022 | Add Agent Studio smoke workflow | Navigation and first operator workflow pass Playwright smoke |

## 3. Sprint Plan

### Sprint 0

Goal: a developer can start the stack and save agent/document metadata.

Scope:

- AF-001 FastAPI skeleton
- AF-002 Next.js shell
- AF-003 PostgreSQL migration base
- AF-004 dev compose stack
- AF-005 Agent/Version tables
- AF-008 Knowledge Source/Document tables
- AF-017 audit event writer draft

Current implementation:

- `apps/api` contains the FastAPI service, metadata routes, SQLAlchemy models, Alembic base, and audit event writer.
- `apps/web` contains the Next.js shell for Overview, Agents, Knowledge, Eval, Audit, and Settings.
- `deploy/compose/docker-compose.dev.yaml` defines Postgres, MinIO, Qdrant, API, and Web services.
- `docs/sprint-0-runbook.md` describes the local run path.

D3 evidence focus:

- AF-019 API contract tests
- AF-020 synthetic corpus schema
- AF-021 compose boot smoke
- AF-022 Agent Studio smoke workflow

D3 evidence added:

- `apps/api/tests/test_metadata_contracts.py`
- `eval/synthetic-corpus/case.schema.json`
- `eval/synthetic-corpus/cases-v0.1.json`
- `eval/harness/run_synthetic_eval.py`
- `eval/harness/tests/test_scorer.py`
- `eval/harness/tests/test_fake_retrieval.py`
- `tools/smoke/compose-smoke.ps1`
- `tools/smoke/eval-corpus-smoke.ps1`
- `tools/smoke/eval-scorer-smoke.ps1`
- `apps/web/tests/smoke.spec.ts`

Verification status:

- Full compose boot passed on 2026-05-10 using an auto-selected web port.
- API HTTP smoke passed for agent create/detail/update/version validate/publish.
- Playwright route smoke passed 7/7 against the compose web service.
- Retrieval preview HTTP smoke passed for Finance vs HR ACL filtering.

### Sprint 1

Goal: synthetic corpus can flow through upload, chunking, fake retrieval, and run trace.

Scope:

- AF-006 Agent CRUD API
- AF-007 version validate/publish
- AF-009 MinIO upload
- AF-010 index job skeleton
- AF-011 TXT/MD parser smoke
- AF-012 vector adapter interface
- AF-013 ACL filter model
- AF-014 retrieval preview API
- AF-015 runtime run API skeleton
- AF-018 synthetic corpus v0.1

Sprint 1 progress:

- AF-013 ACL filter model started in `apps/api/app/domain/acl.py`.
- AF-014 retrieval preview API started at `POST /api/v1/knowledge/retrieval/preview`.
- Contract coverage was added for allowed vs blocked users and deny-by-default documents.

### Sprint 2

Goal: minimal real RAG works with ACL filtering and citations.

Scope:

- One embedding adapter
- One vector store adapter, Qdrant or pgvector
- ACL-aware vector search
- Answer-generation mock or local model gateway
- Citation validator
- Test Chat UI draft
- Run Trace Viewer draft
- ACL/citation golden set execution

## 4. Release Gate

MVP demo requires:

- Agent creation, version publish, and document upload work through UI/API.
- Unauthorized documents are excluded before LLM context construction.
- Answers include citations.
- Run, run_step, retrieval_hit, and audit_event records are stored.
- ACL suite passes 100%.
- Citation coverage is at least 95%.
- Useful answer rate is at least 80%, or gaps are documented in the eval report.

## 5. Open Dependencies

| Dependency | Needed by | Blocks |
|---|---|---|
| Pilot department selection | End of Sprint 0 | Real document list |
| Document owner assignment | End of Sprint 0 | Document level and freshness review |
| Model and embedding availability | Sprint 1 | Real retrieval/generation |
| SSO or authority source | Sprint 1 | Production principal and ACL |
| Closed-net staging environment | Sprint 2 | Offline deployment validation |
