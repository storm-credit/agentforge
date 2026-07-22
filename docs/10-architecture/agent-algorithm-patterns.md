# Agent Forge Agentic Algorithm Patterns

Status: Draft design reference; not a runtime commitment  
Owner: AI Architect / QA-Eval  
Related: #108, #120

## 1. Purpose

This document identifies agentic and RAG algorithm patterns that may inform future designs. A named pattern is not automatically part of the first pilot, an active Product Tool, or a promise to implement a commercial general-agent platform.

The current first-pilot runtime remains a controlled document-RAG flow with authorization, retrieval, generation, citation validation, safe refusal, bounded checks, and trace/audit evidence.

## 2. Adoption Rule

A pattern may enter an Agent Version or runtime design only when:

- it solves a named product/pilot problem;
- a simpler deterministic flow is insufficient;
- permissions and trust boundaries remain explicit;
- loop/step/action budgets are bounded;
- stop and human-escalation behavior is defined;
- state, memory, Tools, and side effects are governed;
- security and evaluation cases cover the new behavior;
- measurable benefit exceeds added cost, latency, complexity, and risk;
- an ADR and Work Order approve the change.

## 3. Pattern Catalogue

### 3.1 ReAct-style Reason/Action Interleaving

Concept:

```text
observe bounded state
→ choose one allowed action
→ execute through governed Tool/Retrieval contract
→ record observation
→ repeat within step/action budget
→ answer/refuse/escalate
```

Potential value:

- combines retrieval/Tool observations with decision steps;
- makes action choice and observation traceable;
- can recover when the first information request is insufficient.

Risks:

- uncontrolled loops and token/latency growth;
- prompt injection steering actions;
- confused-deputy Tool use;
- duplicated or consequential side effects;
- reasoning text mistaken for policy authority.

Agent Forge controls:

- allowed action set comes from Agent Version/Build and Product Tool Registry;
- authorization and target validation occur outside model reasoning;
- maximum steps, attempts, time, and cost are explicit;
- write actions require Tool Contract and approval;
- observations are treated as untrusted input;
- every action/result is a Run Step;
- exhausted budget yields refusal/failure/human escalation.

First-pilot status: `LATER-CANDIDATE`. The current RAG flow does not need open-ended action loops.

Reference pattern: ReAct, commonly described as interleaving reasoning and actions (arXiv:2210.03629).

### 3.2 Reflection / Reflexion-style Feedback Memory

Concept:

```text
attempt bounded task
→ evaluate outcome against explicit criteria
→ generate a short structured lesson
→ store lesson in approved episodic memory
→ use lesson for a later attempt
```

Potential value:

- improves repeated task performance without model fine-tuning;
- preserves failure attribution and corrective guidance.

Risks:

- storing secrets, unauthorized content, or incorrect lessons;
- self-reinforcing false assumptions;
- memory poisoning and unbounded growth;
- bypassing approved prompt/policy versioning.

Agent Forge controls:

- reflection is structured, redacted, classified, and reviewable;
- only allowed memory types are stored;
- memory never grants permissions or changes policy;
- lessons have source/eval references, expiry, owner, and invalidation;
- adoption requires measurable improvement against a fixed baseline;
- repeated failure still escalates after the loop budget.

First-pilot status: `NON-GOAL` for self-modifying runtime memory. Structured delivery retrospectives may use this pattern in the Delivery Harness.

Reference pattern: Reflexion, verbal reinforcement using episodic memory (arXiv:2303.11366).

### 3.3 Self-RAG-style Adaptive Retrieval and Critique

Concept:

- decide whether retrieval is needed;
- retrieve evidence conditionally;
- critique relevance/support/utility;
- generate or revise based on explicit signals.

Potential value:

- avoids unnecessary retrieval;
- may improve grounding when evidence quality varies;
- makes retrieval/support decisions evaluable.

Risks:

- model decides retrieval incorrectly;
- critique signals appear confident but are uncalibrated;
- additional latency/complexity;
- adaptive behavior makes regression analysis harder.

Agent Forge controls:

- authorization is never adaptive: ACL always precedes relevance;
- retrieval decisions cannot expose unauthorized sources;
- critique is bounded and does not override deterministic citation/refusal gates;
- route/model/config and critique signals are traced;
- compare against fixed controlled-RAG baseline using one-variable experiments;
- adopt only if real-corpus gains are material without security regression.

First-pilot status: `LATER-CANDIDATE`; controlled retrieval remains the baseline.

Reference pattern: Self-RAG, adaptive retrieval and self-reflection for generation (arXiv:2310.11511).

### 3.4 Planner / Generator / Critic

Concept:

```text
bounded planner selects intent, sources, route, and allowed actions
→ generator produces candidate answer/output
→ critic validates evidence, schema, citation, and policy
→ at most one bounded repair/rewrite
```

This pattern already influences Agent Forge design, but components may be logical stages rather than separate models or agents.

Controls:

- planner output is a typed plan, not executable authority;
- allowed sources/tools/routes are server-validated;
- critic cannot grant access or waive blocker policy;
- one rewrite by default;
- no-context/refusal can terminate before generation;
- trace captures stage, route, findings, and final decision.

First-pilot status: `CURRENT-LIMITED` as a logical bounded runtime pattern; not an autonomous multi-agent system.

### 3.5 Retrieval / Generation Evaluation Decomposition

Concept:

Evaluate separate dimensions such as:

- context relevance and authorized retrieval;
- context coverage/recall for expected evidence;
- faithfulness/claim support;
- answer relevance/usefulness;
- citation validity;
- safe refusal;
- latency, trace, and policy completeness.

Value:

- attributes failures instead of hiding them in one score;
- identifies whether to change corpus, retrieval, reranker, prompt/model, critic, or policy.

Controls:

- ACL leakage remains a blocker outside aggregate scoring;
- deterministic checks are preferred for access, citation locator, trace, schema, and refusal conditions;
- model-assisted judges are calibrated and supplementary;
- missing cases remain incomplete;
- real and synthetic corpora remain separate.

First-pilot status: `CURRENT-PROVEN` in principle through the existing evaluation harness, with real-corpus evidence still `PILOT-REQUIRED`.

Reference pattern: RAGAS and related RAG evaluation decomposition (arXiv:2309.15217).

### 3.6 State Machine / Contract-first Agent Runtime

Concept:

A runtime is governed by explicit states, typed contracts, authorization, and audit rather than free-form prompt chaining.

Agent Forge application:

- Agent Version, Build, Run, Tool, Approval, Index, Eval, and Release state machines;
- JSON Schema for Tool, Agent Contract, Work Order, Review, Evidence, and Routing;
- code-owned guards for protected transitions;
- model output treated as proposed data/action, not authority;
- terminal outcomes and failure categories are explicit.

First-pilot status: `CURRENT-PROVEN` as the governing design direction; implementation conformance remains requirement-specific.

### 3.7 Harness-driven Observability Loop

Concept:

```text
instrument decision/action/evidence
→ observe failures and review findings
→ attribute cause
→ change one harness/control variable
→ evaluate before/after
→ adopt or revert
```

This applies to project delivery, not only Product Runtime. It supports improvements to Work Orders, roles, Skills, Hooks, tests, and evidence quality.

Controls:

- every harness change states a falsifiable expectation;
- observe false blocks, missed risks, repeated failures, rework, and evidence defects;
- do not maximize automation volume;
- prefer fewer deterministic controls over noisy model-generated process;
- provider adapters remain subordinate to repository policy.

First-pilot status: `ACTIVE` for Delivery Harness evolution, not a user-facing feature.

## 4. Pattern Selection Matrix

| Problem | Preferred first approach | Escalation pattern |
|---|---|---|
| Simple grounded Q&A | Controlled authorized RAG | Self-RAG-style adaptation only after baseline evidence |
| Citation/support defect | Deterministic validator + one critic rewrite | Stronger critic/model only with eval gain |
| Missing information | One additional bounded retrieval step | ReAct-style loop only with explicit need/budget |
| Repeated delivery failure | Failure attribution + human escalation after two occurrences | Structured reflection lesson with review |
| Tool action | Typed Tool Contract and state machine | ReAct-style planning does not bypass approval |
| Complex workflow | Deterministic workflow/state machine | Agentic planning only for uncertain substeps |
| Regression diagnosis | Retrieval/generation/policy decomposition | Model-assisted judge as supplementary evidence |

## 5. Non-goals

- revealing or storing private chain-of-thought as an operational requirement;
- allowing model reasoning to replace policy/authorization;
- open-ended autonomous planning for the first pilot;
- self-modifying prompts, contracts, policies, or security controls;
- unlimited reflection, critic, or retrieval loops;
- activation of Tools merely because a model can call them;
- adopting a paper pattern without product and evaluation evidence.

## 6. Experiment Template

Every algorithm-pattern experiment records:

- requirement/problem and baseline;
- candidate pattern and exact bounded change;
- security and trust impact;
- corpus, models, routes, Index Snapshot, and environment;
- step/token/latency/cost budgets;
- expected measurable benefit;
- blocker and quality metrics;
- case-level failures and attribution;
- complexity/operability impact;
- adopt/revert/defer decision;
- ADR and Evidence Package references.

A pattern that provides no material measurable gain or creates unacceptable complexity/risk is reverted or deferred.