# Agent Forge Docs

이 폴더는 GitHub에서 공유할 공식 산출물 공간이다. Obsidian의 `notes/`는 전문가별 작업장이고, 여기 있는 문서는 설명/검토/공유를 위한 정리본이다.

## Architecture Recovery 기준선

현재 프로젝트를 이해할 때는 아래 문서를 먼저 읽는다.

1. [Product Charter](00-product/product-charter.md) — 제품 정의, 대상, 범위, 비범위, 원칙
2. [Capability Map](00-product/capability-map.md) — 능력을 현재 입증·현재 제한·파일럿 필수·후속 후보·비범위로 분류
3. [Scope and Non-Goals](00-product/scope-and-non-goals.md) — 활성 범위, 조건부 범위, 명시적 제외, 백로그 진입 규칙
4. [Product Glossary](00-product/glossary.md) — 제품·보안·런타임·평가·하니스 용어의 공식 의미
5. [C4 Architecture Baseline](10-architecture/c4-model.md) — Context, Container, Component, Deployment와 소유권
6. [Domain Model](10-architecture/domain-model.md) — 핵심 엔터티, aggregate, 권위 저장소와 관계
7. [Core State Machines](10-architecture/state-machines.md) — Agent Version, Document, Index Job, Run, Approval, Eval/Release 상태 전이
8. [Trust Boundaries and Data Flows](20-security/trust-boundaries-and-data-flows.md) — 신뢰 구간, 주요 데이터 흐름, 위협과 fail-closed 통제
9. [Tool and MCP Governance](20-security/tool-and-mcp-governance.md) — 개발 MCP·제품 MCP 분리와 Tool 승인·실행·감사 규칙
10. [ADR Register](30-decisions/adr-register.md) — 채택·제안·미결정·연기된 아키텍처 결정
11. [Requirement Traceability Matrix](40-delivery/traceability-matrix.md) — 요구사항→결정→컴포넌트→구현→테스트·평가·증거 연결
12. [Release Gates](40-delivery/release-gates.md) — PR·기술 MVP·파일럿·운영 단계별 GO/HOLD/NO-GO 조건
13. [Evidence Package Guide](40-delivery/evidence-package-guide.md) — 완료·릴리스 주장에 필요한 증거 구성
14. [Current State](40-delivery/current-state.md) — 현재 실제 상태와 허용 작업의 SSOT 후보
15. [Architecture Recovery Plan](40-delivery/architecture-recovery-plan.md) — 설계 복구와 하니스 제품화 실행 순서
16. [Delivery Harness](../harness/README.md) — 전문 에이전트, Skills, Hooks, MCP, 검증 루프 운영 원칙
17. [Harness Manifest](../harness/manifest.yaml) — 하니스의 초기 기계 판독 기준선
18. [Tool Contract Schema](../harness/schemas/tool-contract.schema.json) — 제품 Tool Version의 검증 가능한 계약
19. [Evidence Package Schema](../harness/schemas/evidence-package.schema.json) — 완료·릴리스 증거의 기계 판독 계약
20. [Development MCP Registry](../harness/registries/development-mcp.yaml) — 개발 도구 권한과 보호 대상
21. [Product Tool Registry](../harness/registries/product-tools.yaml) — 제품 런타임 도구의 deny-by-default 기준선

위 기준선은 기존 코드와 문서를 폐기하지 않는다. 기존 `docs/status-and-go-no-go.md`는 상세 이력과 증거 로그로 유지하고, `notes/01_PM/WBS.md`는 최초 계획 기준선으로 유지한다.

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
| 제품명 | Agent Forge |
| 성격 | 사내망용 통제형 Agent Builder |
| 1차 제품 경계 | Governed Document RAG Agent Builder |
| 능력 분류 | CURRENT-PROVEN / CURRENT-LIMITED / PILOT-REQUIRED / LATER-CANDIDATE / NON-GOAL |
| 논리 아키텍처 | Control / Runtime / Data / Model / Delivery Plane |
| 권한 원칙 | Authorization before relevance, deny-by-default, fail-closed |
| MCP 경계 | Development MCP와 Product MCP의 registry·credential·network·approval 분리 |
| 제품 Tool | 등록·버전·스키마·risk·side effect·approval·audit 계약 필수 |
| 완료 주장 | Exact candidate + requirement + tests/eval + risk + review를 Evidence Package로 제시 |
| 의사결정 | 자동 검증은 증거이며 최종 GO/HOLD/NO-GO는 책임 있는 사람이 기록 |
| 기술 MVP | GO 가능 |
| 파일럿 | 조직·SSO·실문서·사내모델·폐쇄망 결정 전 HOLD |

## 문서 권위

| 문서 | 역할 |
|---|---|
| `docs/00-product/*` | 제품 목적, 능력 분류, 범위, 공식 용어 |
| `docs/10-architecture/*` | C4, 도메인, 상태 전이 아키텍처 기준선 |
| `docs/20-security/*` | 신뢰 경계, 데이터 흐름, MCP/Tool 보안 정책 |
| `docs/30-decisions/adr-register.md` | 아키텍처 결정 상태와 상세 ADR 생성 트리거 |
| `docs/40-delivery/traceability-matrix.md` | 요구사항별 현재 증거 수준과 남은 증거 |
| `docs/40-delivery/release-gates.md` | 단계별 필수 gate와 blocker 규칙 |
| `docs/40-delivery/evidence-package-guide.md` | 증거 품질과 검토 절차 |
| `docs/40-delivery/current-state.md` | 현재 상태와 다음 허용 작업 |
| `docs/status-and-go-no-go.md` | 상세 구현·패널·검증 이력 |
| `notes/01_PM/WBS.md` | 최초 계획 기준선 |
| `CLAUDE.md` | 현재 저장소의 에이전트 지원 개발 실행 규칙 |
| `harness/manifest.yaml` | 벤더 중립 하니스 정책과 계획 자산 |
| `harness/schemas/tool-contract.schema.json` | Product Tool Version의 규범 계약 |
| `harness/schemas/evidence-package.schema.json` | 완료·릴리스 증거의 규범 계약 |
| `harness/registries/*` | Delivery/Product Tool 경계와 활성화 기준 |

## 전문가 산출물 매핑

| 전문가 | 공식 문서 |
|---|---|
| PM 오케스트레이터 / Product Architect | Product/Architecture Recovery 기준선 전체와 ADR Register |
| 보안 아키텍트 | Security Model, Trust Boundaries, Tool and MCP Governance, ADR Register |
| Runtime/MCP 전문가 | Tool/MCP Governance, Tool Contract Schema, registries |
| QA/Eval / Release Governor | Evaluation Plan, Requirement Traceability Matrix, Release Gates, Evidence Package Guide/Schema |
| 하니스 운영 | Delivery Harness, Harness Manifest, schemas, registries |
