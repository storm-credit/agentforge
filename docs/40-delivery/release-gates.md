# Agent Forge Release Gates

Status: Draft delivery baseline  
Owner: Independent Release Governor / QA-Eval  
Related: #108, #116

## 1. Purpose

Release Gates define the minimum evidence required to move a bounded candidate into another stage. They do not replace accountable human decisions.

A gate applies only to its declared candidate, environment, Agent Build, corpus, model/index configuration, and time window. Passing in development or CI does not automatically pass the same gate for a real pilot or production environment.

## 2. Decision Outcomes

| Outcome | Meaning |
|---|---|
| `GO` | All mandatory gates for the bounded stage pass, accountable owners accept residual risk, and no blocker remains |
| `HOLD` | The candidate may become acceptable, but named evidence, decision, dependency, or remediation is missing |
| `NO-GO` | Risk, value, feasibility, security, integrity, or required control is unacceptable for the proposed stage |

Only named accountable humans record the final outcome. Automated checks provide evidence and may force HOLD/NO-GO when a blocker fails, but cannot self-authorize GO.

## 3. Gate Severity

| Severity | Rule |
|---|---|
| Blocker | Must pass. Cannot be offset by other scores. Waiver requires explicit ADR/risk acceptance and may still be prohibited by policy |
| Critical | Must pass for pilot/production; technical-MVP exceptions require documented scope and must not be represented as pilot-ready |
| Major | Must meet threshold or have approved bounded remediation/limitation that does not undermine a blocker |
| Advisory | Informs prioritization and operations but does not independently block the current stage |

## 4. Gate Sets

### 4.1 Pull Request Gate — Documentation/Harness Policy

| Gate | Severity | Pass condition | Evidence |
|---|---|---|---|
| Scope | Blocker | Changed files remain inside the approved Work Order/slice | Compare result and PR file list |
| No false readiness claim | Blocker | Documents distinguish technical MVP, pilot, and production evidence | Reviewer decision |
| Contract syntax | Critical | JSON/YAML/schema artifacts parse and required links resolve where automated support exists | Schema/parse output or manual verification until automation exists |
| Security boundary | Critical | No new runtime capability, credential, or trust-boundary weakening is introduced unintentionally | Security review |
| Backend CI | Critical | Ruff, migration round trip, and full pytest workflow succeed | GitHub Actions run |
| Frontend CI | Critical | TypeScript check succeeds | GitHub Actions run |
| E2E CI | Critical | Playwright live-backend/PostgreSQL suite succeeds | GitHub Actions run |
| Decision/evidence | Major | ADR/traceability/evidence references are updated when affected | PR checklist and review |

### 4.2 Pull Request Gate — Application Change

In addition to the documentation/harness policy gates:

| Gate | Severity | Pass condition |
|---|---|---|
| Work Order | Blocker | Approved scope, acceptance criteria, required reviewers, and prohibited actions exist before implementation |
| Test first/defect reproduction | Critical | New behavior has a failing test or an explicit reason a test-first approach is not applicable |
| Domain/state conformance | Critical | Aggregate authority and lifecycle transitions match the architecture baseline or a new ADR is accepted |
| Authorization regression | Blocker | No forbidden Principal/document/tool access in affected paths |
| Migration safety | Critical | Forward migration and documented rollback/forward-fix strategy pass |
| Trace/audit | Critical | Required new decisions/actions are observable and redacted |
| Eval impact | Critical | Affected Eval Cases and thresholds run against the candidate |
| Evidence Package | Critical | Scope, change, tests, eval, risks, limitations, and review results are complete |

### 4.3 Technical MVP Gate

| ID | Gate | Severity | Pass condition |
|---|---|---|---|
| TM-01 | Core controlled RAG loop | Blocker | Register/index/configure/publish/query/cite-or-refuse/trace path is repeatably exercised |
| TM-02 | ACL leakage | Blocker | Zero known forbidden-document leakage in the required corpus |
| TM-03 | Authorization-before-relevance | Blocker | Retrieval evidence shows an ACL filter and only authorized candidates reach rerank/model context |
| TM-04 | Safe refusal | Critical | Required no-context/unauthorized/insufficient-evidence cases meet the accepted threshold; current baseline target is at least 95% |
| TM-05 | Citation coverage/validity | Critical | Required grounded-answer cases meet the accepted threshold; current baseline target is at least 95%, with material pilot claims evaluated separately |
| TM-06 | Trace completeness | Critical | Required Run, step, retrieval, route, citation, policy, and terminal evidence fields are present for applicable cases |
| TM-07 | Audit evidence | Critical | Required administrative/security events are persisted and reviewable |
| TM-08 | Backend/frontend/E2E | Critical | Required CI checks pass on the candidate commit |
| TM-09 | No silent external route | Blocker | No unapproved external model/tool route is available or used |
| TM-10 | Known limitations | Major | Technical limitations and non-code blockers are explicit in Current State |

### 4.4 Pilot Entry Gate

Technical MVP gates must remain green. The following additional evidence is mandatory:

| ID | Gate | Severity | Pass condition |
|---|---|---|---|
| PI-01 | Accountable pilot owner | Blocker | Named business owner, department, user population, outcome, and decision authority |
| PI-02 | Approved corpus | Blocker | Document inventory, owners, classification, ACL, retention, and deletion rules approved |
| PI-03 | Real identity | Blocker | Approved SSO/IdP integration, trusted groups/roles, expiry/revocation/outage behavior tested |
| PI-04 | Internal model baseline | Blocker | Chat LLM, embedding, and reranker/no-reranker decision, versions, owners, capacity, data policy, and failure behavior fixed |
| PI-05 | Closed-network staging | Blocker | Target topology, ingress, secrets, storage, database, vector, model routes, and egress controls operational |
| PI-06 | Real-corpus security | Blocker | Zero ACL leakage and no restricted content in unauthorized context, response, trace, or logs |
| PI-07 | Real-corpus quality | Critical | Citation, refusal, and task-quality thresholds accepted by business and QA/Eval owners |
| PI-08 | Performance/capacity | Critical | Accepted concurrency, throughput, error rate, and p95 latency are met on internal endpoints; proposed RAG baseline target remains p95 ≤ 8 seconds until revised by ADR |
| PI-09 | Audit/retention/access | Critical | Retention, access review, redaction, capacity, and incident retrieval are approved/tested |
| PI-10 | Backup/restore | Critical | Accepted RTO/RPO and successful restore/reconciliation exercise |
| PI-11 | Monitoring/support | Critical | Metrics, alerts, on-call/service owner, incident path, and runbooks are exercised |
| PI-12 | Import/supply chain | Critical | Offline import, scans, hashes/signatures, provenance, and internal promotion are verified |
| PI-13 | Release authority | Blocker | Named business, product, security, platform, QA/Eval, and Release Governor roles record GO/HOLD/NO-GO |
| PI-14 | Scope confirmation | Blocker | No consequential write Tools, unrestricted MCP, external SaaS, or autonomous expansion entered the first pilot |

The current project remains `HOLD` for pilot entry until these external/organizational/environmental inputs exist.

### 4.5 Pilot Exit / Broader Rollout Gate

A successful technical pilot is not automatically approval for broader rollout. Exit evidence includes:

- measured user outcome and adoption;
- unresolved-answer and refusal analysis;
- security/ACL incidents and near misses;
- model/index drift and update process;
- operational load, cost, capacity, support burden, and incidents;
- document-owner workflow and SLA;
- audit/compliance review;
- accessibility and user support;
- updated risk assessment;
- rollout/rollback decision and scope.

### 4.6 Production Gate

Production readiness requires environment-specific compliance, operations, capacity, recovery, security testing, change management, support, data governance, and organizational approval. No repository-only document can declare this gate passed.

## 5. Blocker Catalogue

The following are blockers unless a stricter policy already prohibits waiver:

- unauthorized document or Tool access;
- secret or restricted-content exposure;
- untrusted Principal accepted as authorized;
- required ACL filter absent or bypassed;
- unregistered Product Tool/MCP execution;
- consequential action without required exact-action approval;
- silent external model/tool route;
- missing required audit for a success/effect;
- mutable published Build/configuration;
- missing mandatory Eval Cases or falsified/incomplete evidence;
- failing required CI/migration/E2E;
- pilot without named owner, approved documents, real identity, internal models, or staging;
- unknown/partial Tool effect reported as ordinary success;
- direct reuse of development credentials in Product Runtime.

## 6. Threshold Management

1. Thresholds are versioned with the Eval Corpus/baseline.
2. Security blockers such as ACL leakage remain absolute unless an accountable policy decision explicitly changes the requirement; aggregate quality cannot offset them.
3. A threshold change requires rationale, before/after distribution, affected cases, risk analysis, and approvers.
4. Real-corpus calibration may raise or refine quality thresholds but must not hide regressions by deleting difficult cases.
5. Missing/unavailable cases count as incomplete evidence, not automatic passes.
6. Model-assisted scoring is supplementary unless its own reliability and calibration are established; deterministic checks remain preferred for gates.

## 7. Evidence Freshness

| Evidence | Freshness rule |
|---|---|
| CI/tests | Exact candidate commit or documented equivalent rerun |
| Eval | Exact Build/config/model/index/corpus/environment references |
| Security review | Covers current trust boundary and code/config diff |
| Dependency scan/import | Exact artifact digest promoted to target environment |
| Performance | Target-like environment and approved model/storage endpoints |
| Restore test | Current backup format, versions, topology, and runbook |
| Approval | Binds to exact candidate/action and remains unexpired |

## 8. Gate Decision Record

Every stage decision records:

- decision ID and stage;
- candidate commit/release/Build/environment;
- Work Order and requirement IDs;
- gate catalogue version;
- pass/fail/incomplete result for each mandatory gate;
- Evidence Package reference;
- blocker and residual-risk summary;
- limitations and expiry/review conditions;
- approvers and decision timestamp;
- GO/HOLD/NO-GO;
- rollback/disable plan where applicable.

## 9. Release Governor Review

The Independent Release Governor:

- did not implement the candidate being judged;
- verifies the candidate identity and evidence freshness;
- samples raw evidence, not only summaries;
- checks that deferred/non-code dependencies are not marked complete;
- checks that blockers are not diluted by aggregate metrics;
- records missing evidence and conflict of interest;
- recommends GO/HOLD/NO-GO;
- cannot override accountable security/business prohibitions.

## 10. Current Stage Assessment

| Stage | Current assessment | Reason |
|---|---|---|
| Architecture Recovery documentation slices | GO when each PR CI and scope review pass | No runtime capability is added; repository authority is being improved |
| Technical MVP | GO-capable within repository evidence boundary | Existing code, tests, eval, and E2E evidence are substantial |
| First real pilot | HOLD | Pilot owner/docs, real SSO, internal model/reranker baseline, staging, and operations decisions remain open |
| Production | Not assessed / not claimable | Required environment and organizational evidence does not exist in the repository |
