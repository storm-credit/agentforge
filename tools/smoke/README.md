# Smoke Checks

These scripts are D3 evidence helpers for Sprint 0 and Sprint 1.

They are designed to be safe by default. `compose-smoke.ps1` validates compose configuration
without booting containers unless `-Boot` is passed.

## Compose Config Smoke

```powershell
./tools/smoke/compose-smoke.ps1
```

Checks:

- Docker Compose can render `deploy/compose/docker-compose.dev.yaml`.
- Required services are present: `postgres`, `minio`, `qdrant`, `api`, `web`.
- Required host ports are declared.

## Full Boot Smoke

```powershell
./tools/smoke/compose-smoke.ps1 -Boot
```

Checks:

- Builds and starts the local stack.
- Waits for API health endpoints.
- Confirms `/healthz` and `/readyz` respond.
- Confirms the Web root responds.

If port `3000` is already in use, let the script choose a free web port:

```powershell
./tools/smoke/compose-smoke.ps1 -Boot -WebPort 0
```

## Synthetic Corpus Smoke

```powershell
./tools/smoke/eval-corpus-smoke.ps1
```

Checks:

- `cases-v0.1.json` parses as JSON.
- The corpus has 30 cases.
- Suite counts match the Sprint 0 D3 target.
- Expected citations point to known synthetic documents.

## Eval Scorer Smoke

```powershell
./tools/smoke/eval-scorer-smoke.ps1
```

Checks:

- The deterministic scorer runs against all synthetic cases.
- ACL accessibility rules produce expected allow/block outcomes.
- The scorer unit tests pass.

## Indexing Parser Smoke

Run this after the API is available, for example after full compose boot:

```powershell
./tools/smoke/indexing-smoke.ps1
```

Checks:

- A synthetic Markdown document creates an index job.
- TXT/MD parser smoke produces deterministic chunk metadata.
- Fake vector adapter writes deterministic vector refs.
- Chunk metadata responses do not expose raw content.
- Retrieval preview returns chunk citations for authorized users.
- A document without ACL metadata fails closed.

## Real Upload Ingestion Smoke

Run this after the API is available:

```powershell
./tools/smoke/real-ingestion-smoke.ps1
```

Checks:

- A real Markdown file uploads through `POST /api/v1/knowledge/documents/upload`.
- Object storage returns an `object_uri` and SHA-256 checksum.
- Indexing succeeds without synthetic `source_text`.
- Retrieval preview returns the uploaded chunk citation.
- A published agent run stores runtime steps and retrieval hits.

## Web Smoke

```powershell
cd apps/web
npm install
npm run dev
npm run test:e2e
```

Checks:

- Agent Studio shell routes render.
- Operators can navigate Overview, Agents, Knowledge, and Audit.
