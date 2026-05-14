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
