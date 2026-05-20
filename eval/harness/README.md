# Eval Harness

This harness is the first deterministic scorer for Agent Forge synthetic corpus cases.

It does not call an LLM. It checks whether the corpus, ACL expectations, and citation
expectations are internally consistent enough to become D3 evidence.

## Run

From the repository root:

```powershell
python eval/harness/run_synthetic_eval.py
python -m unittest discover eval/harness/tests
```

To run the same corpus against a live API stack:

```powershell
python eval/harness/run_api_synthetic_eval.py --api-base-url http://127.0.0.1:8000/api/v1
python eval/harness/run_api_synthetic_eval.py --case rag_001 --case acl_002
python eval/harness/run_api_synthetic_eval.py --suite acl
```

To record a minimal OpenAI-compatible model probe in the eval report:

```powershell
python eval/harness/run_api_synthetic_eval.py `
  --api-base-url http://127.0.0.1:8000/api/v1 `
  --validation-lane company-quality `
  --model-base-url $env:AGENT_FORGE_MODEL_BASE_URL `
  --model-id $env:AGENT_FORGE_MODEL_ID `
  --model-provider company-vllm `
  --model-endpoint-alias company-qwen35b
```

The probe sends one `/v1/chat/completions` request, records provider/model/endpoint alias,
latency, served model, and a short response preview, and never stores the raw endpoint URL.
`company-quality` requires a successful model probe; `local-regression` may skip it when the
local model is unavailable.

API-backed reports also include `summary.quality_review`. For `company-quality`, this records
`quality-rubric-v0.1`, marks human review as required before release approval, and fixes the
automatic blocker gates for final answer cleanliness (`<think>` markers must not appear),
citation ACL recheck, and endpoint secret redaction. For `local-regression`, the same rubric is
recorded as advisory only because the local 8B lane proves integration and safety regression, not
final answer quality.

The API runner generates Markdown from the synthetic corpus, uploads every document through
`POST /knowledge/documents/upload`, indexes with object storage by omitting `source_text`,
publishes an eval agent, runs cases with corpus principal headers, maps API document IDs back
to corpus document IDs, and prints a JSON pass/fail report. It scores runtime `answer`,
`policy_denied`, `no_context`, and `refuse` outcomes from guardrail state, citations, and
retrieval-hit traces.

## What It Checks

- corpus shape and unique case IDs
- expected citations point to known documents and valid locators
- answer cases cite documents the principal may access
- answer cases do not allow known forbidden citations through ACL
- policy-denied cases target inaccessible known forbidden documents
- fake retrieval keeps forbidden documents out of allowed context and citations
- suite-level pass/fail counts are reported in JSON

This is a seed. Sprint 1 should connect the same case set to real retrieval hits, runtime
answers, citations, trace rows, and audit events.
