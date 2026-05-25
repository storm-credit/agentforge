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

### Current Sprint Model Selection

The orchestrator maps tiers to concrete model profiles for the current Sprint 1/2 work. This is a deployment choice, not a permanent product claim.

| Profile | Backing Model | Provider | Used For | Must Not Be Used For |
|---|---|---|---|---|
| `none-deterministic` | no generative model | local code | ACL filters, schema checks, formatting, scorer gates | judgement or answer generation |
| `local-qwen8b` | `qwen3:8b` via Docker `wset-ollama` | local Ollama OpenAI-compatible endpoint | fast specialist drafts, local-regression smoke, bounded critique | final quality approval |
| `company-qwen35b` | company Qwen3.6 35B via vLLM | company OpenAI-compatible endpoint | release-quality review, Korean business tone, recommendation rationale, deep-review decisions | pre-ACL retrieval, ACL override, raw secret handling |
| `embedding-profile-tbd` | deployment-pinned embedding model | local or company | chunk/query embeddings | user-visible generation |
| `reranker-profile-tbd` | deployment-pinned reranker | local or company | post-ACL reranking | pre-ACL candidate review |

| Specialist Agent | Routine Profile | Escalation Profile | Orchestrator Decision |
|---|---|---|---|
| Orchestrator | `local-qwen8b` | `company-qwen35b` | use 35B for release, contradiction, and go/no-go calls |
| PM Agent | `local-qwen8b` | `company-qwen35b` | use 35B only when pilot acceptance or stakeholder risk changes |
| Chief Architect | `local-qwen8b` for draft analysis, `company-qwen35b` for boundary review | `company-qwen35b` | architecture fitness decisions need deep review |
| Security Architect | `company-qwen35b` | `company-qwen35b` | security defaults to deep-review; no downgrade for ACL/PII/audit |
| AI Runtime Architect | `local-qwen8b` | `company-qwen35b` | runtime/model-policy changes escalate |
| RAG/Data Specialist | `local-qwen8b` | `company-qwen35b` | chunking/retrieval failures escalate |
| Backend Specialist | `local-qwen8b` | `company-qwen35b` | migrations/auth/audit persistence escalate |
| Frontend Specialist | `local-qwen8b` | `local-qwen8b` or `company-qwen35b` for release-gate UI | 35B only when UI affects operator approval or trace interpretation |
| DevOps/MLOps | `local-qwen8b` | `company-qwen35b` | model serving and closed-net release escalate |
| QA/Eval | `local-qwen8b` | `company-qwen35b` | failed-case triage and baseline approval escalate |

Until the company vLLM endpoint is configured, escalation decisions are recorded as pending `company-qwen35b` evidence rather than silently accepted from the local model.

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
| `smoke` | local tests, contract checks, synthetic runner | 3 sec | model calls disabled; deep-review escalation may be declared but is unavailable in smoke execution |
| `standard` | MVP operator workflow | 8 sec | only for critic/security escalation |
| `release-gate` | eval, baseline approval, go/no-go review | 15 sec | allowed and expected |
| `incident` | suspected ACL leak, audit failure, model drift | 30 sec | mandatory |

The default Sprint 1 route is `standard`. Eval baseline approval and failed-case triage use `release-gate`.

## 5. Validation Model Lanes

Agent Forge separates engineering validation from final answer-quality validation.

| Lane | Model Target | Purpose | Required Evidence | Not Accepted As |
|---|---|---|---|---|
| `local-regression` | Local Qwen3 8B or equivalent small local model | integration, safety, ACL/citation regression, timeout handling, trace shape | contract tests, smoke runs, deterministic scorer, safety/refusal checks | final answer-quality approval |
| `company-quality` | Company Qwen3.6 35B through vLLM or internal OpenAI-compatible gateway | final quality and operations validation for Korean business answers | Golden Test pass rate, human review, Korean tone review, recommendation rationale, latency/timeout report | ACL override, citation override, untraced judgement |

Rules:

- Local Qwen3 8B is the default smoke lane for fast iteration. It proves that the platform wiring, safety gates, and regression checks still work.
- Company Qwen3.6 35B/vLLM is the release-quality lane. It proves that the final answer is natural, persuasive, and useful for company work.
- Both lanes must use the same ACL-first retrieval, citation validator, runtime trace, and audit event requirements.
- The company-quality model may receive only authorized chunks, answer drafts, citation records, and trace IDs. It must never see denied chunks, pre-ACL candidates, raw storage URIs, or ACL internals beyond the minimum trace summary needed for review.
- The release report must record lane, provider, endpoint alias, model ID, model version if available, timeout, latency p50/p95, and failed Golden Test cases.
- The exact internal model ID and vLLM endpoint are deployment configuration, not hardcoded policy text.
- Current Sprint 1 runtime still uses synthetic answer generation; these lanes become executable model-serving evidence only after the Model Gateway/vLLM client records concrete provider and model provenance.

## 6. Orchestrator Dispatch Policy

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
| Company vLLM quality lane | AI Runtime + QA/Eval + DevOps/MLOps + Security | `local-regression` first, then `company-quality` release gate | Golden Test report, latency/timeout report, human review, trace/audit evidence |

## 7. Agent Card Integration

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

## 8. D3 Acceptance

Model optimization is accepted only when:

- every runtime stage has an explicit tier
- deterministic controls remain outside model judgement
- high-risk policy decisions can escalate to `deep-review`
- eval reports include validated model route metadata now, and Model Gateway later replaces tier declarations with provider/model/version evidence
- validation lane and concrete model/provider evidence are recorded for local-regression and company-quality runs
- no release gate relies only on a cheap model's unverified judgement
