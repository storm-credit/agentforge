# ADR-114: Config-C retrieval/rerank/evaluation baseline

Status: Proposed (a candidate baseline awaiting re-measurement — not an accepted pilot configuration; see Decision)
Date: 2026-08-22
Owners: Product / RAG / QA-Eval
Related requirements/issues/PRs: PR #89 (post-rerank top-k cutoff, source of the "Config-C" candidate); `docs/eval-results-live-v0.5.md`; ADR-106 (reranker baseline, `Proposed`, same evidence caveat); ADR-104 (internal chat LLM, `OPEN`); ADR-105 (internal embedding model, `OPEN`); ADR-102 (pilot document inventory, `OPEN`)
Supersedes / Superseded by: None

## Context

`docs/30-decisions/adr-register.md` §4 lists ADR-114 ("Config-C retrieval/rerank/evaluation baseline") as `OPEN`, requiring a fixed real-corpus candidate and thresholds. The only candidate configuration measured in this repository is the one from PR #89's live A/B/C experiment (`docs/eval-results-live-v0.5.md`), referred to there and in prior handoffs as "Config C": `retrieval_min_score=0.35`, `rerank_backend=hybrid_lexical`, `rerank_top_k=2`, `answer_min_score=0.53`.

**What is currently in force, verified against the code, not assumed from any `.env` file:**

- `apps/api/app/core/config.py` defines these as `Settings` fields with the following code-level defaults: `retrieval_min_score: float = 0.0`, `answer_min_score: float = 0.0`, `rerank_backend: Literal["none", "hybrid_lexical"] = "none"`, `rerank_top_k: int | None = None`.
- These defaults mean that, absent any environment override, retrieval and answer confidence gating are **both disabled** (threshold 0.0 admits everything) and reranking is off.
- The commonly-cited operating value `AGENT_FORGE_RETRIEVAL_MIN_SCORE=0.53` exists only in `apps/api/.env` (and is documented as the local live-dev setting in `docs/40-delivery/poc-hr-pilot-2026-08-13.md`). `apps/api/.env` is gitignored and is not present in any other checkout, worktree, or CI runner. **It is not authoritative for anyone but the person who set it locally**, and this ADR does not treat it as a repository default.
- `answer_min_score`, which Config-C's refusal-holding result (PR #89, Condition C) depends on, is **not** enabled even in that local `.env`-based PoC (`docs/40-delivery/poc-hr-pilot-2026-08-13.md` §notes it stayed at `0.0`/disabled there). Adopting Config-C therefore requires an explicit new setting, not just continuing current local practice.
- Config-C was measured on `eval/synthetic-corpus/cases-live-v0.3.json` (synthetic, 11 documents / 21 cases) with local `qwen3:1.7b` + `bge-m3`, one run per condition except Condition C (two runs, reproduced).

## Decision Drivers

- A "fixed... baseline" per the register's evidence-required column must be reproducible and must state exact threshold values, not a description like "current defaults," because the code defaults and the commonly-run local configuration are different (see above) and conflating them would misstate what ships.
- Config-C depends on ADR-106 (reranker decision) not being settled yet; this ADR cannot be finalized independently of ADR-106.
- Real-corpus, real-model re-measurement (ADR-102, ADR-104/105) is required before either the retrieval/rerank thresholds or the resulting eval numbers can be treated as a pilot baseline, for the same reasons given in ADR-106.

## Options Considered

### Option A — Adopt Config-C as measured (`retrieval_min_score=0.35`, `rerank_backend=hybrid_lexical`, `rerank_top_k=2`, `answer_min_score=0.53`)

The only option with any in-repo before/after evidence (+8.4pt useful_answer, refusal held, reproduced twice). Not adoptable as-is: measured on a synthetic corpus with a non-production model, and requires enabling `answer_min_score`, which is off even in current local practice.

### Option B — Keep current local practice (`retrieval_min_score=0.53`, no rerank) as the baseline

This is what local live verification has actually been running, but it exists only in a gitignored `.env` file, not in code, and PR #89's own Condition A entry is exactly this configuration reproduced for comparison — it is the pre-existing baseline Config-C was measured against, not a candidate improvement.

### Do nothing / defer

Leaves the pilot with the code defaults (`0.0`/`0.0`/none/unbounded), which admit every retrieved candidate regardless of relevance — not a safe or intentional pilot posture, and not what any measurement in this repository was run against.

## Decision

**No baseline is adopted by this ADR.** Config-C (`retrieval_min_score=0.35`, `rerank_backend=hybrid_lexical`, `rerank_top_k=2`, `answer_min_score=0.53`) is recorded as the sole named candidate, carried forward from PR #89, conditional on:

1. ADR-106 resolving in favor of the hybrid lexical reranker (or a successor with equivalent or better measured effect) — if ADR-106 instead resolves to no-reranker, Config-C's `rerank_*` fields do not apply and only its `retrieval_min_score`/`answer_min_score` pairing would carry forward, itself unverified in that combination;
2. re-measurement on the accepted pilot corpus (ADR-102) with the approved internal chat and embedding models (ADR-104/105), since every number cited above comes from a synthetic corpus and a local `qwen3:1.7b`/`bge-m3` stack that is explicitly not the in-house production model.

This ADR must not be read as fixing these threshold values for the pilot.

## Consequences

Positive: there is a concrete, named, reproducible candidate to re-measure rather than starting from nothing, and its dependency on `answer_min_score` (currently disabled everywhere) is now explicit rather than assumed.

Negative / explicitly open: until re-measured, no threshold value in this ADR may be deployed as a pilot default; doing so would mean shipping a synthetic-corpus, non-production-model result as if it were validated. The gap between code defaults (fully open gates) and the locally-used `.env` value (`0.53`, undocumented anywhere authoritative) is itself an operational risk independent of this ADR — a fresh checkout or CI environment with no `.env` runs with all relevance/confidence gating disabled unless a deployment explicitly sets these values.

## Required Controls and Evidence

- Re-run the PR #89 A/B/C comparison shape against the accepted pilot corpus and internal models before adopting any specific threshold set.
- Whatever configuration is eventually adopted must be set as an explicit, documented deployment-time environment value (not left to the code default, and not left undocumented in a gitignored file) so that CI, staging, and production share a stated baseline.

## Follow-up

- Product / RAG / QA-Eval: re-run the comparison once ADR-102 and ADR-104/105 land, jointly with ADR-106.
- Platform: once a baseline is adopted, document the required `AGENT_FORGE_RETRIEVAL_MIN_SCORE` / `AGENT_FORGE_ANSWER_MIN_SCORE` / `AGENT_FORGE_RERANK_BACKEND` / `AGENT_FORGE_RERANK_TOP_K` values in a non-gitignored deployment reference so they are not dependent on any one operator's local `.env`.
