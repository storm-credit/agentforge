# Agent Forge Requirement Traceability Matrix

Status: Draft delivery baseline  
Owner: PM Orchestrator / QA-Eval  
Related: #108, #116

## 1. Purpose

This matrix links product requirements to architecture decisions, owning components, implementation areas, tests/evaluation, and evidence needed for a completion or release claim.

It is intentionally conservative:

- `VERIFIED-TECHNICAL` means repeatable repository evidence exists within the development/CI boundary.
- `PARTIAL` means implementation or evidence exists but the complete contract is not yet verified.
- `PILOT-EVIDENCE-REQUIRED` means a real identity, corpus, model, environment, or operational decision is still required.
- `DEFERRED` means outside the first-pilot product boundary.
- A code area is a navigation reference, not proof that every requirement is fully implemented there.

## 2. Requirement ID Convention

| Prefix | Area |
|---|---|
| PRD | Product boundary and user outcome |
| IAM | Identity, authorization, and ACL |
| KNO | Knowledge and indexing |
| RAG | Retrieval, generation, citation, and refusal |
| AGV | Agent Version and Build governance |
| RUN | Runtime execution, trace, and audit |
| MOD | Model routing and internal model use |
| EVAL | Evaluation and release gates |
| DEP | Closed-network deployment and operations |
| TOOL | Product Tool and MCP governance |
| DEL | Delivery Harness and evidence governance |

## 3. Product and Scope Requirements

| ID | Requirement | Product/architecture authority | Owning component/domain | Implementation/evidence area | Tests/eval | Status | Remaining evidence |
|---|---|---|---|---|---|---|---|
| PRD-001 | Product shall remain a governed internal document RAG Agent Builder for the first pilot | Product Charter; Scope/Non-goals; ADR-001 | PM Orchestrator / Product Architect | Repository product documents; current application scope | Scope review | `VERIFIED-TECHNICAL` | Accountable pilot owner accepts bounded use case |
| PRD-002 | Technical MVP, Pilot, and Production Ready claims shall remain distinct | Product Glossary; Current State; ADR-012 | PM Orchestrator / Release Governor | Status and release documentation | Release review | `VERIFIED-TECHNICAL` | Pilot and production evidence packages when applicable |
| PRD-003 | Specialists shall not add active product scope without an approved decision | Scope/Non-goals; Harness Manifest | PM Orchestrator | Issue/PR/work-order governance | Scope-conformance review | `PARTIAL` | Work Order schema and automated checks |
| PRD-004 | Later candidates shall not be presented as committed roadmap | Capability Map; Scope/Non-goals | Product | Product/backlog documents | Product review | `VERIFIED-TECHNICAL` | Ongoing governance |

## 4. Identity and Authorization Requirements

| ID | Requirement | Authority | Owner | Implementation/evidence area | Tests/eval | Status | Remaining evidence |
|---|---|---|---|---|---|---|---|
| IAM-001 | Protected operations shall derive Principal identity from a trusted server-side integration | Trust Boundaries TB-02; ADR-003/004 | Security / API | API authentication dependencies and middleware | Auth/permission tests | `PARTIAL` | Real IdP, trusted claims, expiry/revocation/failure tests |
| IAM-002 | Authorization shall be applied before relevance, reranking, and model context | Product principles; C4; Trust flow; ADR-003/011 | Security / RAG | API retrieval orchestration and vector adapter | ACL corpus and leakage gates | `VERIFIED-TECHNICAL` | Real group/document mapping validation |
| IAM-003 | Missing or invalid identity/ACL data shall deny or safely refuse | Trust Boundaries; ADR-004 | Security / Runtime | Authorization/policy path | Negative auth and no-ACL cases | `VERIFIED-TECHNICAL` | IdP outage and stale-group behavior in staging |
| IAM-004 | Vector ACL metadata shall be derived, while authoritative ACL remains in metadata/policy store | Domain Model; ADR-007/008 | Security / Data | PostgreSQL metadata and vector payload adapter | Adapter contract/ACL tests | `VERIFIED-TECHNICAL` | Reconciliation under real backend and corpus |
| IAM-005 | ACL changes shall invalidate or rematerialize derived chunks, vectors, and caches | State Machines; Trust flow | Knowledge / Security | Index/revoke lifecycle | Revoke/delete exclusion tests | `PARTIAL` | Full ACL-change reconciliation and target-environment evidence |
| IAM-006 | Unauthorized content shall not enter reranker input, model context, answer, ordinary logs, or user-visible traces | Trust model; Security Model | Security / RAG / Runtime | Retrieval, trace, and logging paths | ACL leakage and redaction cases | `VERIFIED-TECHNICAL` | Pilot restricted-document scenarios and log inspection |

## 5. Knowledge and Indexing Requirements

| ID | Requirement | Authority | Owner | Implementation/evidence area | Tests/eval | Status | Remaining evidence |
|---|---|---|---|---|---|---|---|
| KNO-001 | A Document requires an accountable owner, classification, and ACL before active indexing | Product Charter; Domain Model; Trust flow | Knowledge Owner / Data | Knowledge/document APIs and index jobs | Ingestion validation cases | `PARTIAL` | Real owner approvals and classification policy |
| KNO-002 | Raw content shall retain checksum and content-version lineage | Domain Model | Data / Backend | Object metadata, document/chunk records | Ingestion fixture tests | `PARTIAL` | Confirm complete persistence/trace mapping |
| KNO-003 | Indexing shall be stateful, stage-aware, retryable only under declared rules, and audited | State Machines | Data / Backend | Index-job worker and records | Worker failure/retry tests | `VERIFIED-TECHNICAL` | Real parser/model/storage failure exercises |
| KNO-004 | Partial index writes shall not become active before reconciliation and snapshot activation | C4; State Machines | Data / RAG | Vector adapter/index generation | Adapter and smoke tests | `PARTIAL` | Confirm generation isolation for selected pilot vector backend |
| KNO-005 | Revocation shall stop retrieval before asynchronous physical deletion completes | Domain/State/Trust baseline | Security / Data | Document revoke and vector delete path | Revoke exclusion test | `VERIFIED-TECHNICAL` | Backup/cache and real-backend reconciliation |
| KNO-006 | An Index Snapshot shall identify the searchable knowledge/configuration state used by a Build | Agent Build Spec; Domain Model; ADR-006 | AI Architecture / Data | Build/index metadata | Build/eval trace review | `PARTIAL` | Full persisted snapshot identity and runtime enforcement |

## 6. RAG Requirements

| ID | Requirement | Authority | Owner | Implementation/evidence area | Tests/eval | Status | Remaining evidence |
|---|---|---|---|---|---|---|---|
| RAG-001 | Retrieval shall use a server-built ACL filter in the query, not only post-filtering | RAG Design; Architecture; ADR-003 | RAG/Data | Vector adapter and retriever | Adapter contract/ACL tests | `VERIFIED-TECHNICAL` | Selected pilot vector backend performance evidence |
| RAG-002 | Reranking shall receive only authorized candidates | Trust baseline; ADR-011 | RAG/Security | Retrieval/rerank orchestration | Leakage cases | `VERIFIED-TECHNICAL` | Approved reranker and real-corpus evidence |
| RAG-003 | Material claims in grounded answers shall have valid citations | Product Charter; Agent Build Spec | Runtime / QA-Eval | Answer/citation validation path | Citation scorer and corpus | `VERIFIED-TECHNICAL` | Real-corpus threshold validation |
| RAG-004 | No authorized or sufficient evidence shall produce safe refusal rather than model improvisation | Product Charter; Scope; ADR-004 | Runtime / Security | Runtime no-context path | Refusal cases | `VERIFIED-TECHNICAL` | Pilot user wording and support acceptance |
| RAG-005 | Citation validation shall check source lineage and support, not merely citation presence | Domain Model; Agent Build Spec | RAG / QA-Eval | Citation validator/critic and trace | Citation support cases | `PARTIAL` | Expand claim-support corpus and false-citation analysis |
| RAG-006 | Critic/rewrite loops shall be bounded | State Machines; Harness loop policy | Runtime | Runtime orchestration | Loop/terminal outcome tests | `PARTIAL` | Verify configured maximum and trace across all routes |

## 7. Agent Version and Build Requirements

| ID | Requirement | Authority | Owner | Implementation/evidence area | Tests/eval | Status | Remaining evidence |
|---|---|---|---|---|---|---|---|
| AGV-001 | Agent configuration shall be versioned | Agent Build Spec; Domain Model | Control Plane / Backend | Agent/version APIs and DB | Version lifecycle tests | `VERIFIED-TECHNICAL` | None within technical MVP boundary |
| AGV-002 | Published Agent Versions and Builds shall be immutable | ADR-005; State Machines | Control Plane / Backend | Publish/build path | Invalid-transition/concurrency tests | `PARTIAL` | Full Build entity enforcement and persistence confirmation |
| AGV-003 | Publish shall atomically establish the intended current version and supersede the previous version | State Machines | Backend | Publish transaction | Concurrent publish tests | `VERIFIED-TECHNICAL` | Staging DB evidence |
| AGV-004 | Validation/approval shall bind to the exact resolved configuration and become stale on change | Build Spec; State Machines | Control / Approval | Validation/build/approval path | Stale revision tests | `PARTIAL` | Approval schema and immutable action/build hash implementation |
| AGV-005 | A disabled/revoked Build shall not start new Runs while historical evidence remains | State Machines | Runtime / Control | Build/run authorization | Disable behavior tests | `PARTIAL` | Build lifecycle implementation mapping |

## 8. Runtime, Trace, and Audit Requirements

| ID | Requirement | Authority | Owner | Implementation/evidence area | Tests/eval | Status | Remaining evidence |
|---|---|---|---|---|---|---|---|
| RUN-001 | Every request shall receive a Run/request correlation and pin Agent/Build/Principal context | Domain Model; State Machines | Runtime / Backend | `/runs` and trace persistence | API/E2E trace cases | `VERIFIED-TECHNICAL` | Full Build pinning verification |
| RUN-002 | Significant authorization, retrieval, route, generation, citation, and terminal steps shall be reconstructable | C4; Domain Model | Runtime / Backend | Run steps, retrieval hits, route traces | E2E trace drill-down | `VERIFIED-TECHNICAL` | Retention/redaction policy in pilot environment |
| RUN-003 | Consequential administrative and security events shall create Audit Events | Domain/State/Trust baselines | Security / Backend | Audit APIs/store | Audit surface and action tests | `VERIFIED-TECHNICAL` | Append/retention/access model in staging |
| RUN-004 | Required audit persistence failure shall prevent success acknowledgement | Agent Build Spec; ADR-004 | Security / Runtime | Runtime finalization | Failure-injection test | `PARTIAL` | Explicit end-to-end fault test and ops behavior |
| RUN-005 | Trace and logs shall redact secrets and minimize classified content | Trust baseline | Security / Platform | Structured logging/trace serializers | Redaction/security tests | `PARTIAL` | Pilot log-store review and secret scanning |
| RUN-006 | Terminal outcomes shall distinguish success, refusal, denial, failure, and cancellation | State Machines | Runtime | Run status/error contract | API/E2E outcome cases | `PARTIAL` | Confirm all implementation status mappings |

## 9. Model Requirements

| ID | Requirement | Authority | Owner | Implementation/evidence area | Tests/eval | Status | Remaining evidence |
|---|---|---|---|---|---|---|---|
| MOD-001 | Model access shall use an approved gateway/adapter and routing policy | ADR-010; C4 | AI Platform / Runtime | Model routing modules and route traces | Routing validation/tests | `VERIFIED-TECHNICAL` | Approved internal endpoints and owner |
| MOD-002 | Model route shall respect task, data classification, availability, and configured failure rules | Build Spec; Tool/Trust model | Runtime / Security | Shared route policy | Policy validation and route traces | `PARTIAL` | Versioned model-routing schema/policy slice |
| MOD-003 | There shall be no silent fallback to an unapproved external provider | Trust boundary TB-06; ADR-018 | Security / Platform | Network/routing configuration | Route and egress tests | `VERIFIED-TECHNICAL` by design | Closed-network staging evidence |
| MOD-004 | Model/provider/version and fallback outcome shall be traceable | Route trace architecture | Runtime | Run route trace | E2E/eval trace | `VERIFIED-TECHNICAL` | Internal endpoint metadata |

## 10. Tool and MCP Requirements

| ID | Requirement | Authority | Owner | Implementation/evidence area | Tests/eval | Status | Remaining evidence |
|---|---|---|---|---|---|---|---|
| TOOL-001 | Development MCP and Product MCP shall have separate registries, credentials, networks, and approvals | Tool/MCP Governance; ADR-013/014 | Security / Delivery / Runtime | `harness/registries/*` | Registry review | `VERIFIED-TECHNICAL` as policy | Provider/runtime enforcement adapters |
| TOOL-002 | Unregistered Product Tool Versions shall not execute | Product Tool Registry; Tool schema | Runtime / Security | Registry currently empty | Schema/policy review | `VERIFIED-TECHNICAL` as deny baseline | Tool executor enforcement before first tool |
| TOOL-003 | Product Tool contracts shall declare schemas, data, permission, risk, side effects, execution, approval, idempotency, audit, and failure behavior | Tool schema/governance | Runtime-MCP / Security | JSON Schema | Schema validation required | `VERIFIED-TECHNICAL` as contract | Add automated schema test in harness slice |
| TOOL-004 | Consequential write tools shall remain prohibited in the first pilot | Scope; Product registry | Product / Security | Empty registry and pilot policy | Scope review | `VERIFIED-TECHNICAL` | New ADR required to change |
| TOOL-005 | Unknown or partial effects shall stop blind retry and enter compensation/escalation | Tool governance; State Machines | Runtime / Domain Owner | Future Tool Executor | Failure scenario tests | `DEFERRED` | Required before any write Tool activation |

## 11. Evaluation and Release Requirements

| ID | Requirement | Authority | Owner | Implementation/evidence area | Tests/eval | Status | Remaining evidence |
|---|---|---|---|---|---|---|---|
| EVAL-001 | Eval cases shall define identity, allowed/forbidden evidence, expected behavior, score, and severity | Evaluation Plan; Domain Model | QA-Eval | `eval/` harness and persisted cases | Corpus/schema tests | `VERIFIED-TECHNICAL` | Real pilot cases |
| EVAL-002 | ACL leakage blocker count shall be zero | Evaluation Plan | Security / QA-Eval | ACL corpus/scorer | Release gate | `VERIFIED-TECHNICAL` | Real restricted corpus |
| EVAL-003 | Citation and refusal quality shall meet defined thresholds | Evaluation Plan | QA-Eval / RAG | Scorers/reports | Release gate | `VERIFIED-TECHNICAL` | Recalibrate with real corpus without weakening blockers |
| EVAL-004 | Required runtime trace shall be complete for evaluated Runs | Evaluation Plan | QA-Eval / Runtime | API-backed eval/trace | Trace gate | `VERIFIED-TECHNICAL` | Pilot retention and observability |
| EVAL-005 | Backend, frontend, migrations, and E2E shall pass before merge/release | Repository CI policy | Platform / QA-Eval | GitHub Actions | Required CI | `VERIFIED-TECHNICAL` | Continue per PR |
| EVAL-006 | Baseline and GO/HOLD/NO-GO decisions require accountable human action | Domain/ADR-016 | Release Governor | Decision/evidence documents | Governance review | `PARTIAL` | Decision schemas and named pilot approvers |

## 12. Deployment and Operations Requirements

| ID | Requirement | Authority | Owner | Implementation/evidence area | Tests/eval | Status | Remaining evidence |
|---|---|---|---|---|---|---|---|
| DEP-001 | Product/model/data zones shall have no direct outbound internet by default | C4; Trust; ADR-018 | Platform / Security | Deployment docs/config areas | Network verification | `PILOT-EVIDENCE-REQUIRED` | Closed-network staging and egress test |
| DEP-002 | Imported packages/images/models shall be scanned, hash/signature verified, and promoted through an internal mirror | C4/Trust | Platform / Security | Offline deployment process | Import audit test | `PILOT-EVIDENCE-REQUIRED` | Actual internal pipeline |
| DEP-003 | Secrets shall use approved secret storage/mount and never be committed or traced | Trust baseline | Platform / Security | Deployment/settings/logging | Secret scan/redaction | `PARTIAL` | Target secret mechanism and audit |
| DEP-004 | Backup/restore and RTO/RPO shall be accepted and tested | ADR-111 | Platform / Business Owner | Runbooks/environment | Restore exercise | `PILOT-EVIDENCE-REQUIRED` | Named values and successful test |
| DEP-005 | Monitoring, alerting, incident, and on-call ownership shall be defined | ADR-112 | Platform / Service Owner | Ops docs/environment | Alert/runbook exercise | `PILOT-EVIDENCE-REQUIRED` | Named systems and owners |
| DEP-006 | Audit retention/access/redaction shall be approved for the pilot | ADR-110 | Security / Compliance | Audit store and ops policy | Access/retention review | `PILOT-EVIDENCE-REQUIRED` | Decision and capacity evidence |

## 13. Delivery Harness Requirements

| ID | Requirement | Authority | Owner | Implementation/evidence area | Tests/eval | Status | Remaining evidence |
|---|---|---|---|---|---|---|---|
| DEL-001 | Work shall be bounded by a Work Order before implementation | Harness baseline | PM Orchestrator | Future schema/instances | Schema validation | `PARTIAL` | Work Order schema and examples |
| DEL-002 | Specialist authority, prohibitions, outputs, review, and stop conditions shall be versioned | Harness Manifest | PM Orchestrator | Future Agent Contracts | Schema validation | `PARTIAL` | Agent Contract schema and role instances |
| DEL-003 | Completion claims shall include an Evidence Package | Recovery Plan | QA-Eval / Release Governor | This slice's schema/guide | Schema validation | `PARTIAL` until merged | Use on subsequent implementation slices |
| DEL-004 | Review/rework loops shall have budgets and human escalation | Harness Manifest | PM Orchestrator | Harness policy | Process review | `VERIFIED-TECHNICAL` as policy | Hook/enforcement adapters |
| DEL-005 | Feature work shall use isolated branches and pass required CI before merge | CLAUDE.md; registry policy | All delivery roles | Git/PR/CI | PR evidence | `VERIFIED-TECHNICAL` | Continue operational discipline |
| DEL-006 | Repository policy shall be durable across models/providers and not depend on conversation memory | Harness baseline; ADR-020 | PM Orchestrator | `harness/` and `docs/` | Onboarding review | `PARTIAL` | Complete schemas, skills, hooks, examples |

## 14. Maintenance Rules

1. Requirement IDs are stable and not reused.
2. A changed requirement updates product authority, ADRs, affected architecture, implementation contract, tests/eval, and this matrix in the same or linked PR.
3. `VERIFIED-TECHNICAL` requires a repeatable repository reference; prose-only intent is `PARTIAL`.
4. Pilot evidence never upgrades a requirement to production readiness outside its environment and scope.
5. A blocker requirement cannot be waived by aggregate score without an accountable ADR/release decision.
6. Release Evidence Packages list the exact requirement IDs in scope and any unresolved mappings.
7. The Release Governor samples evidence rather than trusting checkbox completion alone.