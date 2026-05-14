# Eval and Trace UI Runbook

This runbook describes the current operator workflow after the API-backed synthetic eval runner has executed against a live local stack.

## Current Scope

The API-backed runner is the source of truth for Sprint 1 eval evidence. It uploads the synthetic corpus through public APIs, indexes documents from object storage, publishes an eval agent, runs the 30-case corpus through `POST /api/v1/runs`, emits a JSON report, and stores that report through `POST /api/v1/eval/runs`.

The Agent Studio UI currently provides the operator entry points for eval and trace review:

- `/eval` is the evaluation gate landing page and can sync the latest persisted eval report.
- `/audit` is the governance and trace review landing page.
- `/knowledge` can be used to re-check upload, indexing, and retrieval preview behavior.

Use `/api/v1/eval/overview` or `/api/v1/eval/runs/latest` for the persisted report, and use the `/runs` API endpoints as the detailed trace evidence behind those screens until the full Trace Viewer is wired into the UI.

## Run The Eval And Keep The UI Available

From the repository root:

```powershell
./tools/smoke/api-eval-runner-smoke.ps1 -BootStack -WebPort 0 -KeepStack
```

Use `-KeepStack` for UI review. Without it, the wrapper stops the compose stack after the smoke completes. The compose smoke prints the selected Web port when `-WebPort 0` is used.

If the stack is already running:

```powershell
./tools/smoke/api-eval-runner-smoke.ps1 -ApiBaseUrl "http://127.0.0.1:8000/api/v1"
```

The runner output includes:

- `passed`, `total_cases`, `passed_cases`, and `failed_cases`
- `suite_counts`
- `setup.eval_run_id` after the report is persisted
- `setup.run_token`
- `setup.knowledge_source_id`
- `setup.agent_id`
- `setup.agent_version_id`
- per-case `case_id`, `suite`, `expected_behavior`, `passed`, `findings`, `run_id`, `status`, citation document IDs, retrieval document IDs, and denied retrieval count

## Eval UI Review

1. Open Agent Studio at the Web URL printed by compose, for example `http://127.0.0.1:<web-port>`.
2. Open `Eval` from the primary navigation.
3. Use the page as the current quality-gate landing page for the run.
4. Compare the page's gate categories with the runner report:
   - Retrieval quality maps to retrieval document IDs and denied retrieval counts.
   - Answer groundedness maps to citation document IDs and citation guardrail findings.
   - Policy refusal maps to `policy_denied`, `no_context`, and `refuse` cases.
   - Regression suite maps to total/pass/fail counts and suite counts.

For Sprint 1, any blocker investigation should cite the persisted eval report fields and the runtime trace endpoints behind the affected `run_id`.

## Trace Review

Start from a `run_id` in the runner JSON. If you need to locate recent runs manually:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/runs"
```

Inspect the selected run:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/runs/<run-id>"
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/runs/<run-id>/steps"
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/runs/<run-id>/retrieval-hits"
```

Trace evidence to confirm:

- Answer cases have authorized citations and `guardrail.acl_filter_applied=true`.
- Citation-required answer cases have `guardrail.citation_validation_pass=true`.
- Refusal and denied cases do not expose forbidden documents in citations or retrieval hits.
- Runtime steps show the actual path taken. Standard answered runs include `guard_input`, `retriever`, `generator`, `citation_validator`, and `guard_output`; input-guard refusals stop earlier.
- Retrieval hits include ACL filter snapshots and do not include unauthorized chunks.

Open `Audit` in Agent Studio while reviewing trace evidence. The current page is the governance landing surface; detailed event filtering remains a follow-up to the Audit Explorer.

## Pass Criteria

The workflow passes when:

- `api-eval-runner-smoke.ps1` exits successfully.
- The API-backed eval report has `passed=true`.
- `/api/v1/eval/overview` returns the persisted latest report.
- `/eval` and `/audit` render in Agent Studio.
- At least one passing answer case has inspectable run detail, ordered steps, and retrieval hits.
- Failed or denied cases have trace evidence explaining refusal, no-context, or policy-denied behavior without forbidden citations.

## Follow-Up

Next follow-up is the full Trace Viewer: the trace-review steps should keep `/runs/{run_id}`, `/steps`, and `/retrieval-hits` as the drill-down path, but the UI should make those links first-class from each eval case.
