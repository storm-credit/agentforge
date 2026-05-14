# Agent Model Routing Policy

Agent Forge uses model routing as an orchestration control, not as a free-form model choice. The orchestrator decides which specialist agent needs deep reasoning, which runtime step should stay deterministic, and which work can use a smaller model to protect latency and cost.

This policy applies to two layers:

- Project specialist agents: PM, Architecture, Security, RAG/Data, Backend, Frontend, DevOps/MLOps, QA/Eval.
- Product runtime agents: Security Guard, Planner, Retriever, Answer Generator, Critic, Formatter, Cost/Latency controller.

## 1. Model Tier Catalog

| Tier | Use | Default Behavior | Must Not Be Used For |
|---|---|---|---|
| `deterministic` | schema validation, ACL filtering, scoring, routing tables | no generative model call | ambiguous policy judgement |
| `fast-small` | classification, summarization, extraction, low-risk critique | low temperature, short context, bounded output schema | final answer generation for cited RAG |
| `standard-rag` | grounded answer generation from authorized context | citation-required, moderate context | policy override, ACL decision |
| `deep-review` | security, architecture, release gate, incident triage | slower, deeper reasoning, stricter checklist | high-volume happy path |
| `embedding` | chunk/query vectorization | deterministic version pinning | user-visible generation |
| `reranker` | rank authorized chunks after ACL filter | only receives allowed candidates | pre-ACL candidate review |
| `safe-fallback` | model outage or timeout response | no hidden chain, no fabricated answer | normal answer path |

The important optimization is not "always use the cheapest model." It is: deterministic first, small model for routing, standard model only for grounded generation, deep model only for gated judgement.

## 2. Project Specialist Routing

| Specialist Agent | Default Tier | Escalate To | Escalation Trigger | Output Gate |
|---|---|---|---|---|
| Orchestrator | `fast-small` | `deep-review` | scope conflict, release decision, cross-team contradiction | decision log or dispatch update |
| PM Agent | `fast-small` | `standard-rag` | stakeholder tradeoff, pilot readiness risk | WBS, risk, owner matrix |
| Chief Architect | `standard-rag` | `deep-review` | service boundary, deployment topology, data ownership | architecture fitness criteria |
| Security Architect | `deep-review` | `deep-review` | all ACL, audit, PII, prompt-injection decisions | policy test or threat-model update |
| AI Runtime Architect | `standard-rag` | `deep-review` | agent contract, runtime flow, model policy change | schema/runtime state gate |
| RAG/Data Specialist | `standard-rag` | `deep-review` | chunking, ACL retrieval, citation failure | eval case or parser/retrieval test |
| Backend Specialist | `standard-rag` | `deep-review` | migration, auth boundary, audit persistence | contract/integration test |
| Frontend Specialist | `fast-small` | `standard-rag` | workflow design, operator error state | Playwright or UI runbook evidence |
| DevOps/MLOps | `standard-rag` | `deep-review` | closed-net release, model serving, backup/restore | smoke/runbook evidence |
| QA/Eval | `standard-rag` | `deep-review` | release gate, failed case triage, scorer policy | eval report and failure taxonomy |

Rules:

- A specialist can draft with its default tier, but D3 verification must use the escalation tier when the artifact changes security, release, data, or runtime behavior.
- The orchestrator records the chosen tier when a decision changes scope, gates, or release readiness.
- PM and Frontend should not consume deep-review capacity for routine wording, list cleanup, or UI copy unless it affects acceptance criteria.

## 3. Runtime Agent Routing

| Runtime Agent | Default Tier | Inputs | Output | Efficiency Rule |
|---|---|---|---|---|
| Security Guard pre-check | `fast-small` plus deterministic patterns | user message, auth context, Agent Card | allow/block/risk flags | block obvious injection without retrieval |
| Planner | `fast-small` | allowed intents, pre-check result, Agent Card | intent, retrieval targets, step plan | never generates final answer |
| Retriever | `deterministic`, `embedding`, `reranker` | query, ACL context, index snapshot | allowed chunks and citation candidates | ACL filter before vector/rerank context |
| Answer Generator | `standard-rag` | authorized chunks, prompt refs, output contract | cited answer draft | no citation, no answer |
| Critic | `fast-small`; escalate to `deep-review` for release/eval failures | answer draft, citations, allowed chunks | groundedness and revision decision | one rewrite max before safe failure |
| Security Guard final-check | `fast-small`; escalate to `deep-review` for high-risk content | final answer, citations, audit summary | final allow/mask/block | cannot be skipped |
| Formatter | `deterministic` | approved answer | response envelope | no new facts |
| Cost/Latency Controller | `deterministic` | route trace, budgets, model health | model route and budget trace | can downgrade only before generation |

## 4. Budget Classes

| Budget Class | Target Use | p95 Target | Deep Review Use |
|---|---|---:|---|
| `smoke` | local tests, contract checks, synthetic runner | 3 sec | disabled except security failure triage |
| `standard` | MVP operator workflow | 8 sec | only for critic/security escalation |
| `release-gate` | eval, baseline approval, go/no-go review | 15 sec | allowed and expected |
| `incident` | suspected ACL leak, audit failure, model drift | 30 sec | mandatory |

The default Sprint 1 route is `standard`. Eval baseline approval and failed-case triage use `release-gate`.

## 5. Orchestrator Dispatch Policy

For every non-trivial dispatch, the orchestrator records:

- owning specialist
- artifact to change
- default model tier
- escalation tier
- D3 evidence expected
- stop condition

Current Sprint 1 dispatch:

| Dispatch | Owning Agents | Model Route | Evidence |
|---|---|---|---|
| Persisted eval run API | Backend + QA/Eval | `standard-rag` for implementation, `deep-review` for release gate review | API contracts and persisted report |
| Upload-to-runtime smoke | Backend + RAG + Security + QA | deterministic retrieval/scoring, `standard-rag` for runtime answer | smoke script and run trace |
| Agent Studio eval sync | Frontend + QA | `fast-small` UI update, `standard-rag` workflow review | Next build and route smoke |
| Model policy hardening | Orchestrator + AI Runtime + Security | `deep-review` because it affects runtime routing | this policy and shared contract |

## 6. Agent Card Integration

Agent Card `model_policy` should reference this routing policy and declare a budget class:

```yaml
model_policy:
  routing_profile_ref: "packages/shared-contracts/model-routing-policy.v0.1.json"
  budget_class: "standard"
  stages:
    security_precheck:
      tier: "fast-small"
      temperature: 0.0
      max_tokens: 400
    planner:
      tier: "fast-small"
      temperature: 0.0
      max_tokens: 800
    answer_generator:
      tier: "standard-rag"
      temperature: 0.2
      max_tokens: 2400
    critic:
      tier: "fast-small"
      escalation_tier: "deep-review"
      temperature: 0.0
      max_tokens: 1200
    security_finalcheck:
      tier: "fast-small"
      escalation_tier: "deep-review"
      temperature: 0.0
      max_tokens: 800
  fallback:
    on_timeout: "safe-fallback"
    on_policy_conflict: "deep-review"
    on_model_error: "safe_failure"
```

## 7. D3 Acceptance

Model optimization is accepted only when:

- every runtime stage has an explicit tier
- deterministic controls remain outside model judgement
- high-risk policy decisions can escalate to `deep-review`
- eval reports include validated model route metadata now, and Model Gateway later replaces tier declarations with provider/model/version evidence
- no release gate relies only on a cheap model's unverified judgement
