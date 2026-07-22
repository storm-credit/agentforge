# Agent Forge Docs

이 폴더는 GitHub에서 공유할 공식 산출물 공간이다. Obsidian의 `notes/`는 전문가별 작업장이고, 여기 있는 문서는 설명/검토/공유를 위한 정리본이다.

## Architecture Recovery 기준선

현재 프로젝트를 이해할 때는 아래 문서를 먼저 읽는다.

1. [Product Charter](00-product/product-charter.md) — 제품 정의, 대상, 범위, 비범위, 원칙
2. [Current State](40-delivery/current-state.md) — 현재 실제 상태와 허용 작업의 SSOT 후보
3. [Architecture Recovery Plan](40-delivery/architecture-recovery-plan.md) — 설계 복구와 하니스 제품화 실행 순서
4. [Delivery Harness](../harness/README.md) — 전문 에이전트, Skills, Hooks, MCP, 검증 루프 운영 원칙
5. [Harness Manifest](../harness/manifest.yaml) — 하니스의 초기 기계 판독 기준선

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
| 1차 MVP | 사내 문서 기반 RAG 에이전트 빌더 |
| 핵심 검증 | 권한 기반 검색, 근거 답변, 실행/감사 로그 |
| 기술 MVP | GO 가능 |
| 파일럿 | 조직·SSO·실문서·사내모델·폐쇄망 결정 전 HOLD |
| 후속 확장 | 승인된 Tool Pack/MCP 계약을 전제로 DB, ERP, 그룹웨어, 파일서버, Git |

## 문서 권위

| 문서 | 역할 |
|---|---|
| `docs/00-product/product-charter.md` | 제품 목적·범위·원칙 |
| `docs/40-delivery/current-state.md` | 현재 상태와 다음 허용 작업 |
| `docs/status-and-go-no-go.md` | 상세 구현·패널·검증 이력 |
| `notes/01_PM/WBS.md` | 최초 계획 기준선 |
| `CLAUDE.md` | 현재 저장소의 에이전트 지원 개발 실행 규칙 |
| `harness/manifest.yaml` | 벤더 중립 하니스 정책과 계획 자산 |

## 전문가 산출물 매핑

| 전문가 | 공식 문서 |
|---|---|
| PM 오케스트레이터 | [Product Charter](00-product/product-charter.md), [Current State](40-delivery/current-state.md), [Architecture Recovery Plan](40-delivery/architecture-recovery-plan.md) |
| 오케스트라 총괄 | [Orchestration Plan](orchestration-plan.md), [Agent Operating Model](agent-operating-model.md), [Deep Specialist Audit](deep-specialist-audit.md) |
| PM Agent | [Project Proposal](project-proposal.md), [Use Case Definition](use-case-definition.md) |
| PM Agent / 오케스트라 | [Pilot Readiness](pilot-readiness.md) |
| 수석 아키텍트 | [Architecture](architecture.md) |
| 보안 아키텍트 | [Security Model](security-model.md) |
| AI 아키텍트 | [Agent Build Spec](agent-build-spec.md) |
| RAG 전문가 | [RAG Design](rag-design.md) |
| 프론트엔드 전문가 / 오케스트라 | [Open Design Adoption Review](open-design-adoption.md) |
| 구현 전문가 | [Implementation Plan](implementation-plan.md), [Implementation Backlog](implementation-backlog.md), [Sprint 0 Runbook](sprint-0-runbook.md) |
| QA/Eval | [Evaluation Plan](evaluation-plan.md) |
| 하니스 운영 | [Delivery Harness](../harness/README.md), [Harness Manifest](../harness/manifest.yaml) |
