# Eval and Trace UI Runbook

This runbook describes the current operator workflow after the API-backed synthetic eval runner has executed against a live local stack.

## Current Scope

The API-backed runner is the source of truth for Sprint 1 eval evidence. It uploads the synthetic corpus through public APIs, indexes documents from object storage, publishes an eval agent, runs the 30-case corpus through `POST /api/v1/runs`, and emits a JSON report.

The Agent Studio UI currently provides the operator entry points for eval and trace review:

- `/eval` is the evaluation gate landing page.
- `/audit` is the governance and trace review landing page.
- `/knowledge` can be used to re-check upload, indexing, and retrieval preview behavior.

Until `/api/v1/eval/runs` and the full Trace Viewer are wired into the UI, use the runner JSON and `/runs` API endpoints as the detailed trace evidence behind those screens.

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

For Sprint 1, any blocker investigation should cite the runner JSON fields directly because the Eval page does not yet persist eval-run artifacts.

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
- `/eval` and `/audit` render in Agent Studio.
- At least one passing answer case has inspectable run detail, ordered steps, and retrieval hits.
- Failed or denied cases have trace evidence explaining refusal, no-context, or policy-denied behavior without forbidden citations.

## Follow-Up When Eval API Lands

When `/api/v1/eval/runs` is implemented, update this runbook so the Eval UI points at persisted eval runs and report artifacts rather than transient runner JSON. The trace-review steps should still keep `/runs/{run_id}`, `/steps`, and `/retrieval-hits` as the drill-down path.
