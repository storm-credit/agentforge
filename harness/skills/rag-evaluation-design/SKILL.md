# RAG Evaluation Design Skill

## Trigger

Use when changing corpus, parsing, chunking, embedding, vector backend, ACL materialization, retrieval, reranking, prompts/models, citation validation, refusal, or RAG release thresholds.

## Required Inputs

- exact baseline and candidate configuration;
- corpus and owner/ACL metadata;
- Agent Build/model/index/policy references;
- current Eval Cases and Release Gates;
- expected user task and failure risks.

## Steps

1. Pin corpus, Principal/group contexts, allowed/forbidden evidence, models, routes, Index Snapshot, and environment.
2. State one primary change and falsifiable expected benefit.
3. Define deterministic blocker cases first: ACL leakage, denied access, no-context refusal, citation locator, trace completeness.
4. Define retrieval measures: authorized recall/coverage, relevance, rank, stale/revoked exclusion, rerank contribution.
5. Define generation measures: faithfulness/claim support, citation validity, answer relevance/usefulness, safe refusal.
6. Define performance and operational measures: latency, errors, capacity, missing cases, trace/audit completeness.
7. Run baseline and candidate with the same fixed inputs.
8. Compare case-level and aggregate results and attribute failures.
9. Adopt, revert, or defer; do not weaken blocker gates.

## Outputs

- versioned Eval Cases/corpus plan;
- metrics and thresholds;
- baseline/candidate comparison;
- failure attribution and case-level findings;
- adoption/revert/HOLD recommendation;
- Evidence Package references.

## Checks

- Reranker/model see only authorized chunks.
- Real and synthetic corpus evidence are labeled separately.
- Missing cases are incomplete, not passed.
- Difficult cases are not removed to improve scores.
- Model-assisted judges are calibrated and supplementary where deterministic checks exist.
- One-variable experiment discipline is followed.
- Quality improvement does not offset ACL leakage or security blockers.

## Escalation

Escalate missing document owners/ACL to PM and Knowledge Owners, security leakage to Security, and unresolved model/config decisions to AI Platform/Product owners.

## Stop Conditions

- candidate meets gates with material justified benefit;
- candidate is reverted due to regression/complexity;
- blocker occurs;
- required corpus/model/environment is unavailable;
- experiment budget is exhausted or result is inconclusive.