# ADR-106: Reranker model and whether the pilot baseline uses reranking

Status: Proposed (a recommendation awaiting accountable review — this ADR explicitly does NOT assert that the decision-pack evidence bar is met; see Decision)
Date: 2026-08-22
Owners: RAG/Data / QA-Eval
Related requirements/issues/PRs: PR #31 (rerank interface + no-op hook), PR #71 (hybrid lexical reranker), PR #89 (post-rerank top-k cutoff); `docs/research-reranking-options.md`; `docs/eval-results-live-v0.5.md`; `docs/40-delivery/poc-hr-pilot-2026-08-13.md`; `docs/40-delivery/pilot-decision-pack.md` §7.3; ADR-011 (`ADOPTED`, reranking receives only already-authorized chunks)
Supersedes / Superseded by: None

## Context

`docs/40-delivery/pilot-decision-pack.md` §7.3 requires the pilot to choose one accepted baseline before this can close: either an approved internal reranker with model/version/configuration, or an explicit no-reranker baseline "with evidence that quality remains acceptable" — and that comparison must use "the same real corpus, Principal/ACL contexts, retrieval configuration, and environment," reporting case-level gains/regressions, p95 latency, capacity, and failures.

**None of the evidence the repository currently has meets that bar.** Verified against the repository (2026-08-22):

- `apps/api/app/core/config.py` defines `rerank_backend: Literal["none", "hybrid_lexical"] = "none"` and `rerank_top_k: int | None = Field(default=None, ge=1)`. The default is no reranking, unbounded top-k.
- PR #31 added the rerank interface and a no-op default hook.
- PR #71 added a real, deterministic BM25+RRF hybrid lexical reranker (no model). It was measured, live, to have **zero effect** at the retrieval threshold in force at the time — not because the mechanism is broken, but because too few candidates survived the score gate for reranking to have anything to reorder (root-caused, not assumed).
- PR #89 added an opt-in post-rerank top-k cutoff and ran a live A/B/C experiment (`docs/eval-results-live-v0.5.md`), using `eval/synthetic-corpus/cases-live-v0.3.json` (11 documents / 21 cases — a **synthetic** corpus, not real pilot documents), against a **local `qwen3:1.7b` generation model and `bge-m3` embeddings** — not the in-house `qwen3-30b-a3b` that ADR-104 is expected to select. Findings:
  - Condition A (current defaults: `retrieval_min_score=0.53`, no rerank) reproduced the existing baseline (refusal 88.9, useful_answer 83.3).
  - Condition B (`retrieval_min_score=0.35`, hybrid rerank, `top_k=2`) showed `retrieval_min_score` **also functions as the refusal gate**: lowering it caused 7 of 9 cases that should have been refused to be over-answered (refusal 88.9 → 22.2).
  - Condition C (B plus a separate `answer_min_score=0.53` gate) recovered refusal to 88.9 while raising useful_answer 83.3 → 91.7 (+8.4pt, one case flipped, of 12), with the same result reproduced on a second run. This is the "Config-C" candidate referenced by ADR-114.
- `docs/40-delivery/poc-hr-pilot-2026-08-13.md`, on a separate synthetic corpus (`eval/synthetic-corpus/cases-pilot-hr-v1.json`, `corpus_id: pilot-hr-v1`), found that with `rerank_top_k=None` (the code default), every hit above `retrieval_min_score` is cited — so `citation_pct=100%` there is not evidence that reranking is unnecessary, it is an artifact of the default cutoff being absent. The document explicitly leaves "whether to adopt `rerank_top_k`" open (§4/§5-1, out of scope of that Work Order).
- `docs/research-reranking-options.md` (2026-06-15) recommends a cross-encoder (BGE-reranker-v2-m3, or Qwen3-Reranker for ecosystem alignment with `qwen3-30b-a3b`) served via vLLM, once an internal vLLM deployment exists — that deployment is itself gated on ADR-104/105, and no cross-encoder reranker of any kind has been implemented or measured in this repository.
- ADR-011 (`ADOPTED`) already guarantees that whatever reranker is or is not selected, it receives only already-ACL-authorized chunks; this ADR does not touch that invariant.

## Decision Drivers

- The decision-pack bar (§7.3) requires real-corpus, real-environment, same-configuration evidence with case-level gains/regressions — the repository has none of that; every measurement above used a synthetic corpus and a non-production model.
- `retrieval_min_score` and reranking are coupled in this codebase (Condition B): any reranker/no-reranker decision must be evaluated together with the retrieval-gate and answer-gate configuration, not in isolation.
- Whatever is decided must not weaken ADR-011.

## Options Considered

### Option A — Approved internal cross-encoder reranker

Not implemented. Requires ADR-104/105 (internal model gateway) to land first, plus a real-corpus comparison per §7.3. `docs/research-reranking-options.md` names concrete candidates (BGE-reranker-v2-m3, Qwen3-Reranker) but with no in-repo measurement.

### Option B — No-reranker baseline (current default: `rerank_backend="none"`)

This is what the repository ships today. It has **not** been shown to meet §7.3's "evidence that quality remains acceptable" bar on a real corpus; the `citation_pct=100%` figure cited above is an artifact of an unbounded cutoff, not a demonstration of sufficiency.

### Option C — Hybrid lexical reranker (`rerank_backend="hybrid_lexical"`) with top-k cutoff and a separate answer-confidence gate

Implemented (PR #71, PR #89) and the only option with any in-repo A/B/C measurement, but that measurement is on a synthetic corpus with a non-production model and does not by itself satisfy §7.3.

### Do nothing / defer

The status quo (Option B, by default) is what happens if this ADR is not acted on — which is itself a decision with the evidence gap named above, not a neutral non-choice.

## Decision

**No accepted baseline is selected by this ADR.** The evidence in this repository does not meet the bar `docs/40-delivery/pilot-decision-pack.md` §7.3 sets for either option. This ADR records a provisional recommendation only: Option C's configuration (hybrid lexical rerank + top-k cutoff + a separate `answer_min_score` gate, i.e. the "Config-C" shape) is the most promising *starting point* for re-measurement, because it is the only configuration with any measured, reproduced, non-regressing improvement in this repository — but that improvement is a single case (of 12) on a synthetic corpus with a local `qwen3:1.7b`, and **must be re-measured on the real pilot corpus (ADR-102) and the approved internal model (ADR-104) before it can be treated as a decision.** This ADR must not be read as a GO for hybrid reranking, nor as a GO for no-reranker.

## Consequences

Positive: the interface exists (PR #31) so whichever option is chosen requires configuration, not new architecture; ADR-011's authorization invariant is unaffected either way.

Negative / explicitly open: the pilot cannot claim §7.3 is satisfied. Re-measurement against a real corpus and the approved internal model is a hard prerequisite, and the outcome could go either way — the +8.4pt result might not reproduce, and `retrieval_min_score` acting as a de facto refusal gate is a design coupling that needs its own review regardless of the reranker choice.

## Required Controls and Evidence

- Re-run the same A/B/C comparison shape from `docs/eval-results-live-v0.5.md` on the accepted pilot corpus (ADR-102) and the approved internal chat/embedding models (ADR-104/105), with case-level gains/regressions, p95 latency, and failure reporting as §7.3 requires.
- Any reranker candidate must be verified not to receive unauthorized chunks (ADR-011), consistent with the current interface contract.

## Follow-up

- RAG/Data / QA-Eval: re-run the retrieval/rerank comparison once ADR-102 (real corpus) and ADR-104/105 (internal models) are decided; this is also ADR-114's prerequisite.
- Product: decide separately whether `retrieval_min_score` doubling as a refusal gate is acceptable long-term, or whether the answer-confidence gate (`answer_min_score`) should be the sole refusal control — this surfaced as a side effect of the PR #89 experiment and is not resolved by this ADR.
