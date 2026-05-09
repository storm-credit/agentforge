# Sprint 0 Runbook

This runbook starts the first executable Agent Forge skeleton. It is intentionally small:
metadata persistence, UI shell navigation, and local infrastructure only.

## 1. Local Stack

From the repository root:

```powershell
docker compose -f deploy/compose/docker-compose.dev.yaml up --build
```

Expected services:

| Service | URL | Purpose |
|---|---|---|
| Web | `http://localhost:3000` | Agent Studio shell |
| API | `http://localhost:8000` | FastAPI service |
| API docs | `http://localhost:8000/docs` | OpenAPI explorer |
| MinIO console | `http://localhost:9001` | Object storage admin |
| Qdrant | `http://localhost:6333` | Vector store |
| Postgres | `localhost:5432` | Metadata database |

## 2. API Checks

```powershell
curl http://localhost:8000/healthz
curl http://localhost:8000/readyz
```

The compose command runs `alembic upgrade head` before the API server starts.

## 3. Metadata Smoke Path

Create an agent:

```powershell
curl -X POST http://localhost:8000/api/v1/agents `
  -H "Content-Type: application/json" `
  -H "X-Agent-Forge-User: local-admin" `
  -d "{\"name\":\"Policy Assistant\",\"purpose\":\"Answer internal policy questions\",\"owner_department\":\"Operations\"}"
```

Create a knowledge source:

```powershell
curl -X POST http://localhost:8000/api/v1/knowledge/sources `
  -H "Content-Type: application/json" `
  -d "{\"name\":\"Pilot Policies\",\"owner_department\":\"Operations\",\"default_confidentiality_level\":\"internal\"}"
```

## 4. Sprint 0 Exit Criteria

- API, Web, Postgres, MinIO, and Qdrant boot from compose.
- `/healthz`, `/readyz`, and OpenAPI respond.
- Agent, agent version, knowledge source, document, and audit tables migrate.
- Agent and knowledge source metadata can be saved through API calls.
- Follow-up Sprint 1 stories are ready for CRUD, upload, parser, fake retrieval, and trace work.

## 5. D3 Evidence Checks

Run the safe smoke checks from the repository root:

```powershell
./tools/smoke/compose-smoke.ps1
./tools/smoke/eval-corpus-smoke.ps1
./tools/smoke/eval-scorer-smoke.ps1
```

API contract tests:

```powershell
cd apps/api
python -m pytest
```

Web route smoke after starting the Next.js dev server:

```powershell
cd apps/web
npm install
npm run dev
npm run test:e2e
```

Current D3 evidence seed:

- API metadata contract tests: `apps/api/tests/test_metadata_contracts.py`
- Synthetic ACL/citation corpus: `eval/synthetic-corpus/cases-v0.1.json`
- Deterministic eval scorer: `eval/harness/run_synthetic_eval.py`
- Compose smoke helper: `tools/smoke/compose-smoke.ps1`
- Corpus smoke helper: `tools/smoke/eval-corpus-smoke.ps1`
- Scorer smoke helper: `tools/smoke/eval-scorer-smoke.ps1`
- Agent Studio route smoke: `apps/web/tests/smoke.spec.ts`
