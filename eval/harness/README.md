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

## What It Checks

- corpus shape and unique case IDs
- expected citations point to known documents and valid locators
- answer cases cite documents the principal may access
- answer cases do not allow known forbidden citations through ACL
- policy-denied cases target inaccessible known forbidden documents
- suite-level pass/fail counts are reported in JSON

This is a seed. Sprint 1 should connect the same case set to real retrieval hits, runtime
answers, citations, trace rows, and audit events.

