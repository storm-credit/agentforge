# Agent Forge Docs

이 폴더는 GitHub에서 공유할 공식 산출물 공간이다. Obsidian의 `notes/`는 전문가별 작업장이고, 여기 있는 문서는 설명·검토·공유를 위한 정리본이다.

## 현재 권위 문서 읽는 순서

1. [Product Charter](00-product/product-charter.md)
2. [Capability Map](00-product/capability-map.md)
3. [Scope and Non-Goals](00-product/scope-and-non-goals.md)
4. [Product Glossary](00-product/glossary.md)
5. [Current State — Authoritative SSOT](40-delivery/current-state.md)
6. [First-Pilot Decision Pack](40-delivery/pilot-decision-pack.md)
7. [Architecture Recovery Completion Report](40-delivery/recovery-completion-report.md)
8. [Architecture Recovery Plan](40-delivery/architecture-recovery-plan.md)
9. [C4 Architecture Baseline](10-architecture/c4-model.md)
10. [Domain Model](10-architecture/domain-model.md)
11. [Core State Machines](10-architecture/state-machines.md)
12. [Model Routing Policy](10-architecture/model-routing-policy.md)
13. [Agentic Algorithm Patterns](10-architecture/agent-algorithm-patterns.md)
14. [Trust Boundaries and Data Flows](20-security/trust-boundaries-and-data-flows.md)
15. [Tool and MCP Governance](20-security/tool-and-mcp-governance.md)
16. [ADR Register](30-decisions/adr-register.md)
17. [Requirement Traceability Matrix](40-delivery/traceability-matrix.md)
18. [Release Gates](40-delivery/release-gates.md)
19. [Evidence Package Guide](40-delivery/evidence-package-guide.md)
20. [Delivery Harness](../harness/README.md)
21. [Harness Manifest](../harness/manifest.yaml)
22. [Specialist Agent Catalog](../harness/agents/specialists.yaml)
23. [Model Routing Policy Asset](../harness/policies/model-routing.yaml)
24. [Lifecycle Hook Policy](../harness/policies/hooks.md)
25. [Hook Policy Manifest](../harness/hooks/policy.yaml)
26. [Bounded Engineering Loops](../harness/policies/engineering-loops.md)
27. [Work Order Example](../harness/examples/work-order.yaml)
28. [Evidence Package Example](../harness/examples/evidence-package.yaml)
29. [Product Baseline Review Skill](../harness/skills/product-baseline-review/SKILL.md)
30. [Architecture Decision Review Skill](../harness/skills/architecture-decision-review/SKILL.md)
31. [Threat Modeling Skill](../harness/skills/threat-modeling/SKILL.md)
32. [RAG Evaluation Design Skill](../harness/skills/rag-evaluation-design/SKILL.md)
33. [API Contract Review Skill](../harness/skills/api-contract-review/SKILL.md)
34. [Migration Verification Skill](../harness/skills/migration-verification/SKILL.md)
35. [Release Governance Skill](../harness/skills/release-governance/SKILL.md)
36. [Agent Contract Schema](../harness/schemas/agent-contract.schema.json)
37. [Work Order Schema](../harness/schemas/work-order.schema.json)
38. [Review Result Schema](../harness/schemas/review-result.schema.json)
39. [Model Routing Schema](../harness/schemas/model-routing-policy.schema.json)
40. [Tool Contract Schema](../harness/schemas/tool-contract.schema.json)
41. [Evidence Package Schema](../harness/schemas/evidence-package.schema.json)
42. [Development MCP Registry](../harness/registries/development-mcp.yaml)
43. [Product Tool Registry](../harness/registries/product-tools.yaml)

위 기준선은 기존 코드와 문서를 폐기하지 않는다. `docs/status-and-go-no-go.md`는 상세 구현·패널·검증 이력, `notes/01_PM/WBS.md`는 최초 계획 기준선으로 유지한다.

## 현재 결론

| 항목 | 결정 |
|---|---|
| 제품 경계 | 폐쇄망용 Governed Internal Document RAG Agent Builder |
| 기술 MVP | GO-capable — repository evidence boundary |
| Architecture Recovery | COMPLETE — repository design/governance assets |
| Harness Productization | COMPLETE — repository foundation/contracts/policies/Skills; provider adapters and CI validators remain future implementation |
| 첫 실제 파일럿 | HOLD — accountable owner, documents, SSO, models, staging, operations, release decisions required |
| Production readiness | Not assessed; not claimable |
| 능력 분류 | CURRENT-PROVEN / CURRENT-LIMITED / PILOT-REQUIRED / LATER-CANDIDATE / NON-GOAL |
| 논리 아키텍처 | Control / Runtime / Data / Model / Delivery Plane |
| 권한 원칙 | Authorization before relevance, deny-by-default, fail-closed |
| MCP 경계 | Development MCP와 Product MCP의 registry·credential·network·approval 분리 |
| 전문가 역할 | 10개 역할을 Agent Contract 구조로 고정하고 Product Runtime 권한은 부여하지 않음 |
| 작업 시작 | Accepted Work Order와 측정 가능한 acceptance criteria가 필요 |
| 모델 라우팅 | approved model/task/classification/failure policy only; silent external fallback 금지 |
| Hook 권위 | provider-neutral repository policy가 기준이며 provider adapter는 하위 구현 |
| Engineering Loop | Design / Build / Eval / Operations / Review 모두 budget·stop·revert·escalation 필수 |
| 알고리즘 패턴 | ReAct·Reflection·Self-RAG 등은 검증된 필요와 ADR가 있을 때만 채택하는 후보 |
| 완료 주장 | Exact candidate + requirements + tests/eval + risks + reviews를 Evidence Package로 제시 |
| 최종 의사결정 | 자동 검증은 증거이며 GO/HOLD/NO-GO는 책임 있는 사람이 기록 |
| 다음 유효 작업 | Pilot Decision Pack의 사람·데이터·ID·모델·환경 결정을 완료한 뒤 direct blocker Work Order 생성 |

## 문서 권위

| 자산 | 역할 |
|---|---|
| `docs/00-product/*` | 제품 목적, 능력, 범위, 공식 용어 |
| `docs/40-delivery/current-state.md` | 현재 상태와 허용 작업의 최종 SSOT |
| `docs/40-delivery/pilot-decision-pack.md` | 첫 Pilot Entry에 필요한 사람·데이터·ID·모델·환경·운영 결정 |
| `docs/40-delivery/recovery-completion-report.md` | 복구 완료 범위, 비증명 영역, 다음 순서 |
| `docs/10-architecture/*` | C4, 도메인, 상태 전이, 모델 라우팅, Agentic 패턴 적용 경계 |
| `docs/20-security/*` | 신뢰 경계, 데이터 흐름, MCP/Tool 정책 |
| `docs/30-decisions/adr-register.md` | 결정 상태와 상세 ADR 생성 트리거 |
| `docs/40-delivery/traceability-matrix.md` | 요구사항별 현재 증거와 남은 파일럿 증거 |
| `docs/40-delivery/release-gates.md` | PR·MVP·Pilot·Production gate와 blocker 규칙 |
| `docs/40-delivery/evidence-package-guide.md` | 증거 품질, 검토, GO/HOLD/NO-GO 절차 |
| `harness/agents/specialists.yaml` | 전문가 역할의 권한·금지·산출물·종료 조건 |
| `harness/schemas/*` | Agent, Work Order, Review, Tool, Evidence, Model Routing 계약 |
| `harness/policies/*` 및 `harness/hooks/*` | 모델 라우팅, Hook, Engineering Loop의 normative policy |
| `harness/skills/*` | 반복 가능한 전문가 워크플로와 검증·승격·중단 조건 |
| `harness/registries/*` | Development/Product Tool 경계와 활성화 기준 |
| `CLAUDE.md` | 현재 저장소에서 적용 중인 provider-specific 실행 규칙 |

## 기존 공식·역사 문서

1. [Project Overview](project-overview.md)
2. [Project Proposal](project-proposal.md)
3. [Use Case Definition](use-case-definition.md)
4. [Pilot Readiness](pilot-readiness.md)
5. [Orchestration Plan](orchestration-plan.md)
6. [Agent Operating Model](agent-operating-model.md)
7. [Deep Specialist Audit](deep-specialist-audit.md)
8. [Open Design Adoption Review](open-design-adoption.md)
9. [Architecture](architecture.md)
10. [Security Model](security-model.md)
11. [Agent Build Spec](agent-build-spec.md)
12. [RAG Design](rag-design.md)
13. [Implementation Plan](implementation-plan.md)
14. [Implementation Backlog](implementation-backlog.md)
15. [Sprint 0 Runbook](sprint-0-runbook.md)
16. [Evaluation Plan](evaluation-plan.md)
17. [Status and Go/No-Go History](status-and-go-no-go.md)

## 전문가 산출물 매핑

| 전문가 | 공식 자산 |
|---|---|
| PM Orchestrator | Product/Delivery 기준선, Current State, Pilot Decision Pack, Work Order, Harness Manifest |
| Product Architect | C4, Domain Model, State Machines, ADR Register, Completion Report |
| Security & Trust | Security Model, Trust/Data Flows, Tool/MCP Governance, Threat Modeling Skill |
| RAG/Data | RAG Design, Traceability RAG requirements, Evaluation Plan, RAG Evaluation Design Skill |
| Runtime/MCP | Tool Contract, Product Tool Registry, runtime/tool state models, Hook policy |
| Backend | Accepted Work Order, API Contract Review Skill, 구현·테스트 Evidence |
| Frontend | Accepted Work Order와 UI·권한·E2E Evidence |
| Platform | Migration Verification Skill, 배포·복구·운영 Evidence |
| QA/Eval | Evaluation Plan, Traceability, Release Gates, Evidence Package, RAG Evaluation Skill |
| Independent Release Governor | Review Result, Release Governance Skill, GO/HOLD/NO-GO recommendation |
