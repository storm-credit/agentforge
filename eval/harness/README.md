# Eval Harness

Two complementary harnesses live here:

- **Live harness — `run_live_eval.py` (current, release-gate).** Drives the running API end to end
  (sources → documents → index → agent → runs) against the real pipeline (Qdrant + bge-m3 + LLM) and
  scores live behavior: `acl_pass_pct`, `citation_pct`, `useful_answer_pct`, `leak_free_pct`,
  `refusal_discipline_pct`, plus `latency_p50_ms`/`latency_p95_ms` (from each run's own `latency_ms`)
  and `trace_completeness_pct` (percentage of runs that produced all five expected trace step types:
  `guard_input`, `retriever`, `generator`, `citation_validator`, `guard_output`), and `faithfulness_pct`
  (percentage of runs whose backend lexical `grounding_score` — read from the `guard_output` trace step —
  is at or above `AGENT_FORGE_EVAL_GROUNDING_MIN`, default `0.0` = the backend code default; set it to
  your live deployment's `AGENT_FORGE_GROUNDING_MIN` to track drift toward the guard threshold; `None`
  when no run reported a grounding score). This is what CLAUDE.md
  means by "before/after 수치". Default corpus `eval/synthetic-corpus/cases-live-v0.1.json` (override
  with `AGENT_FORGE_EVAL_CORPUS`, e.g. `cases-live-v0.2.json` or `cases-live-v0.3.json` — v0.3 expands
  the deny-class corpus from 3 to 9 cases for a more statistically stable `refusal_discipline_pct`).
- **Synthetic structure scorer — `run_synthetic_eval.py` (deterministic, no LLM).** Checks whether the
  synthetic corpus (`cases-v0.1.json`), ACL expectations, and citation expectations are internally
  consistent enough to become D3 evidence. It does not exercise retrieval or generation.

## Run

From the repository root:

```powershell
# Live eval (requires the API + Qdrant + model stack running)
python eval/harness/run_live_eval.py

# Synthetic structure scorer (hermetic, no services)
python eval/harness/run_synthetic_eval.py
python -m unittest discover eval/harness/tests
```

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
