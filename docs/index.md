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
11. [Current State](40-delivery/current-state.md) — 현재 실제 상태와 허용 작업의 SSOT 후보
12. [Architecture Recovery Plan](40-delivery/architecture-recovery-plan.md) — 설계 복구와 하니스 제품화 실행 순서
13. [Delivery Harness](../harness/README.md) — 전문 에이전트, Skills, Hooks, MCP, 검증 루프 운영 원칙
14. [Harness Manifest](../harness/manifest.yaml) — 하니스의 초기 기계 판독 기준선
15. [Tool Contract Schema](../harness/schemas/tool-contract.schema.json) — 제품 Tool Version의 검증 가능한 계약
16. [Development MCP Registry](../harness/registries/development-mcp.yaml) — 개발 도구 권한과 보호 대상
17. [Product Tool Registry](../harness/registries/product-tools.yaml) — 제품 런타임 도구의 deny-by-default 기준선

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
| Craft AI 관계 | 참고 개념. 직접 의존 전제 아님 |
| 핵심 검증 | 권한 기반 검색, 근거 답변, 실행/감사 로그 |
| 능력 분류 | CURRENT-PROVEN / CURRENT-LIMITED / PILOT-REQUIRED / LATER-CANDIDATE / NON-GOAL |
| 논리 아키텍처 | Control / Runtime / Data / Model / Delivery Plane |
| 권한 원칙 | Authorization before relevance, deny-by-default, fail-closed |
| MCP 경계 | Development MCP와 Product MCP의 registry·credential·network·approval 분리 |
| 제품 Tool | 등록·버전·스키마·risk·side effect·approval·audit 계약 필수 |
| 1차 파일럿 Tool | consequential write tool 금지 |
| 기술 MVP | GO 가능 |
| 파일럿 | 조직·SSO·실문서·사내모델·폐쇄망 결정 전 HOLD |

## 문서 권위

| 문서 | 역할 |
|---|---|
| `docs/00-product/*` | 제품 목적, 능력 분류, 범위, 공식 용어 |
| `docs/10-architecture/c4-model.md` | 시스템·컨테이너·컴포넌트·배포 책임과 경계 |
| `docs/10-architecture/domain-model.md` | 핵심 도메인 엔터티, aggregate, 관계와 권위 |
| `docs/10-architecture/state-machines.md` | 상태 전이, guard, invalid transition, audit 요구 |
| `docs/20-security/trust-boundaries-and-data-flows.md` | 신뢰 경계와 데이터 흐름별 통제 |
| `docs/20-security/tool-and-mcp-governance.md` | MCP/Tool onboarding, 실행, 승인, 실패, 감사 정책 |
| `docs/30-decisions/adr-register.md` | 아키텍처 결정 상태와 상세 ADR 생성 트리거 |
| `docs/40-delivery/current-state.md` | 현재 상태와 다음 허용 작업 |
| `docs/status-and-go-no-go.md` | 상세 구현·패널·검증 이력 |
| `notes/01_PM/WBS.md` | 최초 계획 기준선 |
| `CLAUDE.md` | 현재 저장소의 에이전트 지원 개발 실행 규칙 |
| `harness/manifest.yaml` | 벤더 중립 하니스 정책과 계획 자산 |
| `harness/schemas/tool-contract.schema.json` | Product Tool Version의 규범 계약 |
| `harness/registries/development-mcp.yaml` | Delivery Plane 도구 승인 기준 |
| `harness/registries/product-tools.yaml` | Product Runtime Tool 활성화 기준 |

## 전문가 산출물 매핑

| 전문가 | 공식 문서 |
|---|---|
| PM 오케스트레이터 / Product Architect | Product/Architecture Recovery 기준선 전체와 ADR Register |
| 수석 아키텍트 | [Architecture](architecture.md), [C4 Architecture Baseline](10-architecture/c4-model.md), [Domain Model](10-architecture/domain-model.md), [Core State Machines](10-architecture/state-machines.md) |
| 보안 아키텍트 | [Security Model](security-model.md), [Trust Boundaries and Data Flows](20-security/trust-boundaries-and-data-flows.md), [Tool and MCP Governance](20-security/tool-and-mcp-governance.md), [ADR Register](30-decisions/adr-register.md) |
| Runtime/MCP 전문가 | [Tool and MCP Governance](20-security/tool-and-mcp-governance.md), [Tool Contract Schema](../harness/schemas/tool-contract.schema.json), MCP/Tool registries |
| AI 아키텍트 | [Agent Build Spec](agent-build-spec.md) |
| RAG 전문가 | [RAG Design](rag-design.md) |
| QA/Eval | [Evaluation Plan](evaluation-plan.md) |
| 하니스 운영 | [Delivery Harness](../harness/README.md), [Harness Manifest](../harness/manifest.yaml), [Development MCP Registry](../harness/registries/development-mcp.yaml) |
