# Agent Forge Docs

이 폴더는 GitHub에서 공유할 공식 산출물 공간이다. Obsidian의 `notes/`는 전문가별 작업장이고, 여기 있는 문서는 설명/검토/공유를 위한 정리본이다.

## Architecture Recovery 기준선

현재 프로젝트를 이해할 때는 아래 문서를 먼저 읽는다.

1. [Product Charter](00-product/product-charter.md)
2. [Capability Map](00-product/capability-map.md)
3. [Scope and Non-Goals](00-product/scope-and-non-goals.md)
4. [Product Glossary](00-product/glossary.md)
5. [C4 Architecture Baseline](10-architecture/c4-model.md)
6. [Domain Model](10-architecture/domain-model.md)
7. [Core State Machines](10-architecture/state-machines.md)
8. [Model Routing Policy](10-architecture/model-routing-policy.md)
9. [Trust Boundaries and Data Flows](20-security/trust-boundaries-and-data-flows.md)
10. [Tool and MCP Governance](20-security/tool-and-mcp-governance.md)
11. [ADR Register](30-decisions/adr-register.md)
12. [Requirement Traceability Matrix](40-delivery/traceability-matrix.md)
13. [Release Gates](40-delivery/release-gates.md)
14. [Evidence Package Guide](40-delivery/evidence-package-guide.md)
15. [Current State](40-delivery/current-state.md)
16. [Architecture Recovery Plan](40-delivery/architecture-recovery-plan.md)
17. [Delivery Harness](../harness/README.md)
18. [Harness Manifest](../harness/manifest.yaml)
19. [Specialist Agent Catalog](../harness/agents/specialists.yaml)
20. [Model Routing Policy Asset](../harness/policies/model-routing.yaml)
21. [Work Order Example](../harness/examples/work-order.yaml)
22. [Agent Contract Schema](../harness/schemas/agent-contract.schema.json)
23. [Work Order Schema](../harness/schemas/work-order.schema.json)
24. [Review Result Schema](../harness/schemas/review-result.schema.json)
25. [Model Routing Schema](../harness/schemas/model-routing-policy.schema.json)
26. [Tool Contract Schema](../harness/schemas/tool-contract.schema.json)
27. [Evidence Package Schema](../harness/schemas/evidence-package.schema.json)
28. [Development MCP Registry](../harness/registries/development-mcp.yaml)
29. [Product Tool Registry](../harness/registries/product-tools.yaml)

위 기준선은 기존 코드와 문서를 폐기하지 않는다. `docs/status-and-go-no-go.md`는 상세 이력과 증거 로그, `notes/01_PM/WBS.md`는 최초 계획 기준선으로 유지한다.

## 기존 공식 문서 읽는 순서

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

## 현재 결정

| 항목 | 결정 |
|---|---|
| 제품 경계 | 폐쇄망용 Governed Document RAG Agent Builder |
| 능력 분류 | CURRENT-PROVEN / CURRENT-LIMITED / PILOT-REQUIRED / LATER-CANDIDATE / NON-GOAL |
| 논리 아키텍처 | Control / Runtime / Data / Model / Delivery Plane |
| 권한 원칙 | Authorization before relevance, deny-by-default, fail-closed |
| MCP 경계 | Development MCP와 Product MCP의 registry·credential·network·approval 분리 |
| 전문가 역할 | 10개 역할을 Agent Contract 구조로 고정하고 Product Runtime 권한은 부여하지 않음 |
| 작업 시작 | Accepted Work Order와 측정 가능한 acceptance criteria가 필요 |
| 리뷰 | Severity·disposition·evidence를 가진 Review Result 사용 |
| 모델 라우팅 | 승인된 모델·task·classification·실패 정책만 허용하며 silent external fallback 금지 |
| 완료 주장 | Exact candidate + requirements + tests/eval + risks + reviews를 Evidence Package로 제시 |
| 최종 의사결정 | 자동 검증은 증거이며 GO/HOLD/NO-GO는 책임 있는 사람이 기록 |
| 기술 MVP | GO 가능 |
| 파일럿 | 조직·SSO·실문서·사내모델·폐쇄망 결정 전 HOLD |

## 문서 권위

| 자산 | 역할 |
|---|---|
| `docs/00-product/*` | 제품 목적, 능력, 범위, 공식 용어 |
| `docs/10-architecture/*` | C4, 도메인, 상태 전이, 모델 라우팅 |
| `docs/20-security/*` | 신뢰 경계, 데이터 흐름, MCP/Tool 정책 |
| `docs/30-decisions/adr-register.md` | 결정 상태와 ADR 생성 트리거 |
| `docs/40-delivery/*` | 현재 상태, 추적성, gate, 증거, 실행 순서 |
| `harness/agents/specialists.yaml` | 전문가 역할의 권한·금지·산출물·종료 조건 |
| `harness/schemas/*` | Agent, Work Order, Review, Tool, Evidence, Model Routing 계약 |
| `harness/policies/model-routing.yaml` | 벤더 중립 라우팅 기준선과 미결정 pilot 모델 placeholder |
| `harness/registries/*` | Development/Product Tool 경계와 활성화 기준 |
| `CLAUDE.md` | 현재 저장소에서 적용 중인 provider-specific 실행 규칙 |

## 전문가 산출물 매핑

| 전문가 | 공식 자산 |
|---|---|
| PM Orchestrator | Product/Delivery 기준선, Work Order, Harness Manifest |
| Product Architect | C4, Domain Model, State Machines, ADR Register |
| Security & Trust | Security Model, Trust/Data Flows, Tool/MCP Governance |
| RAG/Data | RAG Design, Traceability RAG requirements, Evaluation Plan |
| Runtime/MCP | Tool Contract, Product Tool Registry, runtime/tool state models |
| Backend/Frontend/Platform | Accepted Work Order와 해당 구현·검증 증거 |
| QA/Eval | Evaluation Plan, Traceability, Release Gates, Evidence Package |
| Independent Release Governor | Review Result, Evidence Package, GO/HOLD/NO-GO recommendation |
