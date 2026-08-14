# Eval Harness

Two complementary harnesses live here:

- **Live harness — `run_live_eval.py` (current, release-gate).** Drives the running API end to end
  (sources → documents → index → agent → runs) against the real pipeline (Qdrant + bge-m3 + LLM) and
  scores live behavior: `acl_pass_pct`, `citation_pct`, `useful_answer_pct`, `leak_free_pct`,
  `refusal_discipline_pct`, plus `latency_p50_ms`/`latency_p95_ms` (from each run's own `latency_ms`)
  and `trace_completeness_pct` (percentage of runs that produced all five expected trace step types:
  `guard_input`, `retriever`, `generator`, `citation_validator`, `guard_output`), and `lexical_overlap_pct`
  (percentage of runs whose backend lexical `grounding_score` — read from the `guard_output` trace step —
  is at or above `AGENT_FORGE_EVAL_GROUNDING_MIN`, default `0.0` = the backend code default; set it to
  your live deployment's `AGENT_FORGE_GROUNDING_MIN` to track drift toward the guard threshold; `None`
  when no run reported a grounding score). **Named for what it measures, not "faithfulness":**
  `grounding_score` is a lexical substring-overlap check between the answer and the context, and it is
  defeated by construction when the context itself is attacker-authored (document-borne prompt
  injection) — a fully hijacked run can and does read 100% on this metric. See
  `apps/api/app/domain/grounding.py` and `docs/40-delivery/live-demo-evidence-2026-08-12.md` section 5.
  This is what CLAUDE.md
  means by "before/after 수치". Default corpus `eval/synthetic-corpus/cases-live-v0.1.json` (override
  with `AGENT_FORGE_EVAL_CORPUS`, e.g. `cases-live-v0.2.json` or `cases-live-v0.3.json` — v0.3 expands
  the deny-class corpus from 3 to 9 cases for a more statistically stable `refusal_discipline_pct`).
- **Ingestion format is part of the measurement (WO-2026-08-14-EVAL-FORMAT-COVERAGE).** A corpus
  document may declare `"ingestion_format"`. `markdown` is the default and takes the unchanged
  register + index-job path, so every pre-existing corpus makes byte-identical requests and its
  recorded baselines stay comparable. `docx` is ingested for real: the harness generates a `.docx`
  in memory (headings as Word heading *styles*, never literal `##` text) and posts it as a file to
  `POST /knowledge/documents/upload`, the same endpoint an administrator uses. This matters because
  the product's `chunker_mime_type_for` maps PDF and DOCX to `text/plain`, so heading detection
  never runs on them: measured live on 2026-08-14, six HR policies indexed as markdown produced 21
  chunks all carrying a clause path, and the same six as DOCX produced 6 chunks with none — every
  DOCX citation reads `<title> / body / lines 1-13`. Reports therefore carry
  `format_coverage` + `format_qualification` at the top level and an `ingestion_formats` block with
  `by_format` (the same metrics per format) and `citation_structure` (chunk/structured-chunk counts,
  converter chain and warning codes read out of the product's own recorded lineage,
  `index_job.ingestion` — never recomputed here, so the harness and the product cannot disagree).
  **A run whose documents were all markdown is labelled `markdown-only` with an explicit best-case
  qualification** instead of presenting an unqualified number. PDF is deliberately not supported:
  nothing in the dependency set WRITES a PDF, and a hand-rolled one with Korean text would measure
  the fixture generator rather than the product. Format-paired corpus:
  `eval/synthetic-corpus/cases-pilot-hr-format-v1.json` (the pilot's questions asked of both
  formats; the two copies are ACL-isolated so they cannot compete in retrieval).
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
