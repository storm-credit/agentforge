# Agent Forge First-Pilot Decision Pack

Status: HOLD — accountable inputs required  
Decision stage: First real pilot entry  
Owner: Accountable Business Owner / PM Orchestrator / Independent Release Governor  
Related: #108, #122

## 1. Decision Requested

Decide whether Agent Forge may move from a repository-verified technical MVP into a real departmental pilot using approved internal users, documents, identity, models, infrastructure, and operating controls.

The current recommendation is **HOLD**. The repository design, implementation, tests, evaluation, and delivery governance are substantial, but the human, data, identity, model, environment, and operations inputs required for a real pilot have not been supplied or approved.

HOLD is not a judgment that the technical MVP failed. It means the proposed pilot candidate is not yet completely defined or supported by target-environment evidence.

## 2. Pilot Boundary

The first pilot is limited to:

- one named department and accountable business owner;
- a bounded user population;
- approximately 30–100 owner-approved internal documents, or another explicitly approved bounded corpus;
- authenticated question answering through real enterprise Principal/group context;
- permission-aware retrieval before relevance, reranking, or model context;
- an approved internal chat LLM, embedding model, and reranker or approved no-reranker baseline;
- cited answers or safe refusal;
- trace, audit, evaluation, monitoring, backup, support, and release evidence;
- closed-network staging.

The first pilot excludes:

- consequential write Tools;
- autonomous multi-agent Product Runtime;
- arbitrary MCP servers;
- external SaaS models or Tools;
- company-wide automatic document discovery;
- public multi-tenant SaaS;
- direct ERP, database, email, calendar, groupware, file-server, source-control, financial, access-control, or production-operation effects.

## 3. Decision Summary

| Decision area | ADR | Accountable owner | Current status | Evidence required | Effect on pilot |
|---|---|---|---|---|---|
| Department, business owner, users, and measurable outcome | ADR-101 | Sponsor / Product Owner | OPEN | Named owner, users, use case, success measures, risk/decision authority | Blocker — HOLD |
| Document inventory, owners, classification, ACL, retention, deletion | ADR-102 | Business Owner / Knowledge Owners / Security | OPEN | Approved inventory and owner/group/retention records | Blocker — HOLD |
| Enterprise SSO/IdP and group claims | ADR-103 | Security / Platform | OPEN | Protocol/config, trusted claims, expiry/revocation/outage tests | Blocker — HOLD |
| Internal chat LLM | ADR-104 | AI Platform | OPEN | Model/version/endpoint, owner, capacity, data policy, latency/failure evidence | Blocker — HOLD |
| Internal embedding model | ADR-105 | AI Platform / RAG | OPEN | Model/version/dimensions, throughput, migration and support | Blocker — HOLD |
| Reranker or approved no-reranker baseline | ADR-106 | RAG/Data / QA-Eval | OPEN | Real-corpus quality/latency comparison and owner | Blocker — HOLD |
| Vector backend | ADR-107 | Platform / RAG/Data | OPEN | Qdrant or pgvector decision, ACL query, backup/restore, capacity | Blocker — HOLD |
| Object storage | ADR-108 | Platform | OPEN | Approved store, access, checksum, retention, backup/restore | Blocker — HOLD |
| Closed-network staging topology | ADR-109 | Platform / Security | OPEN | Ingress, zones, secrets, storage, egress, capacity, ownership | Blocker — HOLD |
| Audit retention, access, redaction, and sink | ADR-110 | Security / Compliance / Platform | OPEN | Retention/access/capacity/redaction and review procedure | Critical — HOLD |
| Backup, restore, RTO, and RPO | ADR-111 | Platform / Business Owner | OPEN | Accepted values and successful restoration/reconciliation exercise | Critical — HOLD |
| Monitoring, alerting, incident, and on-call ownership | ADR-112 | Platform / Service Owner | OPEN | SLOs, metrics, alerts, escalation, runbooks, named owners | Critical — HOLD |
| Pilot release approvers and separation of duties | ADR-113 | Sponsor / Security / Release Governor | OPEN | Named roles, RACI, emergency disable/rollback authority | Blocker — HOLD |
| Retrieval/rerank/evaluation Config-C baseline | ADR-114 | Product / RAG / QA-Eval | OPEN | Fixed real corpus, metrics, latency, comparison, decision rationale | Blocker — HOLD |

## 4. Business and User Decision Sheet

Required inputs:

| Field | Required decision/evidence | Status |
|---|---|---|
| Pilot department | One named organizational boundary | OPEN |
| Accountable business owner | Person/role authorized to accept outcome and risk | OPEN |
| Service/product owner | Owner after technical delivery and during pilot | OPEN |
| User population | Named groups/roles and expected user count | OPEN |
| Primary user problem | One bounded problem that document RAG can address | OPEN |
| Excluded use cases | Explicit list, including write/action requests | OPEN |
| Success measures | Accuracy/usefulness, refusal quality, adoption, time saved, support load, security | OPEN |
| Pilot duration and review date | Start/end or decision trigger | OPEN |
| User support route | Contact, response target, escalation | OPEN |
| Business GO/HOLD/NO-GO authority | Named approver(s) | OPEN |

Minimum success measures should include:

- no unauthorized document exposure;
- accepted citation and refusal quality on the real corpus;
- measured user usefulness for the approved task;
- acceptable p95 latency, capacity, and error rate;
- manageable document-owner and support workload;
- no unresolved blocker incident;
- explicit decision on continuation, rollback, or broader rollout.

## 5. Document and Data Decision Sheet

For every pilot document or approved document group, record:

- stable inventory ID and title;
- Knowledge Source;
- accountable Document Owner;
- content version/checksum and source location;
- data classification;
- allowed Principal groups/roles and deny rules;
- retention, deletion, and legal-hold conditions;
- allowed model routes and trace/log restrictions;
- supported parser/type and size;
- update/re-index/revoke owner and service expectation;
- approval date and expiry/review condition.

Required dataset-level evidence:

- inventory completeness review;
- no ownerless documents;
- no default-open ACL;
- real identity group mapping;
- revoked/stale document exclusion tests;
- classified-content redaction/log review;
- deletion and derived-index reconciliation procedure;
- approved Eval Cases containing allowed and forbidden evidence expectations.

## 6. Identity and Authorization Decision Sheet

ADR-103 must define:

| Topic | Required decision/evidence |
|---|---|
| Protocol | OIDC, SAML gateway, reverse-proxy identity, or approved alternative |
| Issuer/audience/trust | Trusted issuer, audience, keys/certificates, validation owner |
| Principal identifier | Stable subject mapping and privacy/retention treatment |
| Group/role claims | Claim names, semantics, nested/dynamic groups, size limits |
| Session/token lifetime | Expiry, renewal, idle timeout, clock tolerance |
| Revocation and role changes | Expected propagation and cache invalidation |
| Failure behavior | IdP outage, invalid token, missing group, stale claim — deny/fail closed |
| Administrative roles | Operator, Knowledge Owner, auditor, platform, release roles |
| Service identities | Workers/model/storage access and least privilege |
| Tests | positive, negative, expired, revoked, missing group, forged client headers, outage |

Pilot GO is prohibited if the runtime accepts client-supplied identity headers as production authority.

## 7. Internal Model Baseline

### 7.1 Chat LLM

Record:

- approved provider/gateway, model ID and version;
- support owner and incident route;
- allowed classifications;
- context and output limits;
- timeout, concurrency, throughput, and capacity;
- p50/p95 latency and error behavior;
- deterministic/reproducibility settings where applicable;
- safe failure/refusal behavior;
- update/deprecation procedure;
- data retention and model-serving log policy;
- no external fallback verification.

### 7.2 Embedding model

Record:

- model ID/version and dimensions;
- language/domain quality evidence;
- chunk/input limits;
- throughput and indexing duration;
- version-change and re-index migration strategy;
- storage/vector compatibility;
- support and capacity owner.

### 7.3 Reranker decision

Choose one accepted baseline:

- approved internal reranker with model/version/configuration; or
- explicit no-reranker baseline with evidence that quality remains acceptable.

Compare using the same real corpus, Principal/ACL contexts, retrieval configuration, and environment. Report case-level gains/regressions, p95 latency, capacity, and failures. Reranking never receives unauthorized chunks.

## 8. Closed-Network Staging Decision Sheet

Required environment decisions:

| Area | Required decision/evidence |
|---|---|
| Platform | Approved VM/container/Kubernetes or other internal runtime |
| Ingress | Internal hostname, TLS, access zone, administrative path |
| Network | Application/data/model/operations/import allowlists and direct egress denial |
| Secrets | Approved secret store/mount, rotation, audit, emergency revoke |
| PostgreSQL | Version, sizing, HA as required, migrations, access, backup |
| Vector store | Selected backend, ACL-filter contract, collections, backup/restore, operations owner |
| Object store | Selected backend, encryption, checksum, retention, backup/restore |
| Model gateway/endpoints | Network paths, health checks, timeout/capacity |
| Audit/log/metrics | Internal destinations, access, retention, redaction, alerts |
| Controlled import | Package/image/model sources, scans, signatures/hashes, SBOM/provenance, promotion |
| Environment ownership | Service, platform, database, model, security, and incident owners |
| Disable/rollback | Build disable, deployment rollback, data/index reconciliation |

Required tests:

- direct outbound internet denied;
- only allowlisted model/data/operations routes work;
- secret scanning and redaction;
- clean install and upgrade from approved artifacts;
- backend/frontend/E2E on target configuration;
- model/vector/object/database dependency failures;
- backup and full restoration/reconciliation;
- alert delivery and incident escalation;
- emergency Build/Agent disable.

## 9. Audit, Retention, and Privacy Decisions

Define separately for:

- raw Documents;
- chunks/index metadata and embeddings;
- Run input/output and citations;
- Run Steps, route and retrieval traces;
- Audit Events;
- evaluation fixtures/results/reports;
- operational logs and metrics;
- backups;
- identity references.

For each, decide:

- classification;
- authoritative store and access roles;
- fields retained or redacted;
- retention and deletion timeline;
- integrity/append expectations;
- export/review procedure;
- capacity monitoring;
- incident/legal-hold behavior;
- restore implications.

Credentials, raw tokens, private keys, connection strings, and secret headers are never retained in these stores.

## 10. Real-Pilot Evaluation Package

The candidate evaluation must pin:

- exact application commit/release and Agent Build;
- real approved corpus version and ACL mapping;
- SSO/Principal/group test identities;
- chat LLM, embedding, reranker/no-reranker references;
- retrieval/chunking/Config-C policy;
- vector/object/database environment;
- Eval Corpus and baseline version;
- route and security policy versions.

Mandatory evidence:

| Gate | Required result |
|---|---|
| ACL leakage | Zero forbidden-document leakage in mandatory cases |
| Authorization-before-relevance | Only authorized candidates reach reranker/model context |
| Safe refusal | Accepted threshold; existing minimum baseline is 95% until revised by approved decision |
| Citation/support | Accepted threshold; existing minimum baseline is 95% until real-corpus calibration is approved |
| Trace completeness | Required Run, retrieval, route, policy, citation, and terminal evidence present |
| Audit | Required administrative/security events retained and reviewable |
| Revocation/staleness | Revoked/stale content absent from results, context, response, trace, and logs |
| Performance | Accepted concurrency/error/throughput and p95 latency; proposed baseline remains p95 ≤ 8 seconds until revised by ADR |
| Capacity/stability | Sustained expected user/indexing load without uncontrolled degradation |
| Failure behavior | IdP, model, vector, object, DB, audit, timeout and dependency failures safely handled |
| Regression | No new blocker and accepted comparison to technical baseline |

Model-assisted judging may supplement but does not replace deterministic ACL, citation locator, trace, schema, and refusal checks.

## 11. Operations and Support Decisions

Required named ownership and evidence:

- service owner and business owner;
- platform/on-call owner;
- database, vector, object, and model dependency owners;
- Knowledge Owner support route;
- security incident route;
- SLOs and alert thresholds;
- user support and response targets;
- known-issue and status communication;
- backup schedule and restoration owner;
- release/rollback/disable authority;
- incident severity and escalation matrix;
- post-incident review and regression-test process.

A repository runbook without named target-environment ownership is not sufficient for Pilot GO.

## 12. Release Roles and Decision Record

Required roles, with separation where appropriate:

| Role | Decision responsibility | Named? |
|---|---|---:|
| Accountable Business Owner | Outcome, users, business risk, continuation | No |
| PM/Product Owner | Scope, success measures, exclusions, sequence | No |
| Security Owner | Identity, ACL, data, audit, residual security risk | No |
| Platform/Service Owner | Environment, support, backup, monitoring, recovery | No |
| AI Platform Owner | Internal models, capacity, failure, update lifecycle | No |
| Knowledge Owner(s) | Documents, classification, ACL, retention | No |
| QA/Eval Owner | Corpus, gates, results, regression, missing evidence | No |
| Independent Release Governor | Candidate/evidence/gate verification and recommendation | Role defined; human not named |

Decision record:

| Field | Current value |
|---|---|
| Candidate | Not fully defined |
| Evidence Package | Not available for real pilot |
| Mandatory blockers | Open ADR-101 through ADR-114 as applicable |
| Recommendation | HOLD |
| Final accountable decision | Pending |
| Safe current state | Technical MVP retained; feature freeze; no real pilot activation |

## 13. Permitted Next Work

Before the human decisions above, no speculative feature expansion is allowed.

After one or more decisions are supplied, create separate accepted Work Orders only for work directly needed to:

- integrate real SSO/IdP;
- onboard approved documents and ACL mappings;
- configure approved internal models and routing;
- establish selected vector/object/storage backends;
- deploy closed-network staging;
- implement or verify audit/retention/backup/monitoring/import controls;
- close real-corpus security/quality/performance gaps;
- remediate a critical security, data-integrity, deployment, migration, trace, or evaluation defect.

Each Work Order must reference requirement IDs, ADR decisions, acceptance criteria, reviewers, verification, Evidence Package, stop conditions, and rollback/disable behavior.

## 14. GO / HOLD / NO-GO Rule

- **GO** only when all Blocker gates and required Critical gates pass for the exact pilot candidate and named accountable owners approve.
- **HOLD** when a credible pilot remains possible but required decisions, owners, data, environment, models, or evidence are incomplete.
- **NO-GO** when risk, value, feasibility, security, data governance, operations, or required controls are unacceptable.

Current state: **HOLD**.