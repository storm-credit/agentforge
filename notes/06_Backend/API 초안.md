# API 초안

## Agent Registry

- `GET /agents`
- `POST /agents`
- `GET /agents/{agent_id}`
- `POST /agents/{agent_id}/versions`
- `POST /agents/{agent_id}/publish`

## Documents

- `POST /knowledge-sources`
- `POST /documents`
- `POST /documents/{document_id}/index`
- `GET /documents/{document_id}`

## Runtime

- `POST /runs`
- `GET /runs/{run_id}`
- `GET /runs/{run_id}/steps`

## Audit

- `GET /audit-events`
- `GET /tool-calls`

