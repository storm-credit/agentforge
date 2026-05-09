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

## Synthetic Corpus Smoke

```powershell
./tools/smoke/eval-corpus-smoke.ps1
```

Checks:

- `cases-v0.1.json` parses as JSON.
- The corpus has 30 cases.
- Suite counts match the Sprint 0 D3 target.
- Expected citations point to known synthetic documents.

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
