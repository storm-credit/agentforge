# Agent Version Lifecycle UI (slice 3/4)

Adds an agent **detail page** (`/agents/[id]`) that surfaces the existing backend version
lifecycle (`draft → validated → published`) in the frontend. Backend was already complete
(`GET /agents/{id}`, `GET /agents/{id}/versions`, `POST /agents/versions/{id}/validate|publish`);
this slice is frontend wiring only — no new backend.

## What was added
- `apps/web/app/lib/api.ts`: `getAgent`, `listVersions`, `validateVersion`; `publishVersion` now
  takes an optional `reason`.
- `apps/web/app/agents/[id]/page.tsx`: version list (v#, status badge, created_by, published_at) with
  per-version **검증(validate)** / **게시(publish)** actions and a required-reason input (audited).
- `apps/web/app/agents/page.tsx`: agent cards now link to the detail page.
- `apps/web/tests/agent-version-lifecycle.spec.ts`: Playwright render smoke.

## Out of scope (backlog)
- "Create new version" from the detail page: the backend `POST /agents/versions` hardcodes
  `version: 1`, so a second version collides on the `(agent_id, version)` unique constraint.
  Version creation still works via `/agents/new`. Auto-incrementing version numbers is a backend
  follow-up.
- Rollback / version diff views.

## Verification (2026-06-14, live stack)
- `tsc --noEmit`: clean.
- Playwright: **12 passed** (incl. the new lifecycle smoke), `PLAYWRIGHT_BASE_URL=http://127.0.0.1:3300`.
- Manual browser run (preview, port 3300) on a fresh draft agent "Version Demo Agent":
  - draft → clicked **검증** with reason → status became **validated** (deterministic, from API response).
  - validated → clicked **게시** with reason → status became **published**; action buttons correctly
    disappeared (published has no further transition). No console errors.
- Honesty: UI state is a direct render of the API response, so the transition signal is deterministic.
  Audit rows for validate/publish are written by the existing backend endpoints (verified by their
  contract tests in `test_metadata_contracts.py`).
