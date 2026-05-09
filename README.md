# Agent Forge

사내망 환경을 위한 통제형 AI 에이전트 빌더 플랫폼.

Agent Forge는 승인된 모델, 사내 문서, 업무 시스템 도구, 권한정책, 감사 로그를 조합해 업무용 AI 에이전트를 생성하고 운영하기 위한 프로젝트입니다.

## MVP

1차 MVP는 사내 문서 기반 RAG 에이전트 빌더입니다.

- 문서 수집과 인덱싱
- 권한 기반 문서 검색
- 근거 citation 답변
- 에이전트 카드 설정
- 실행 로그와 감사 로그
- 최소 Agent Studio UI

## Obsidian Vault

이 저장소는 Obsidian Vault로도 사용할 수 있습니다.

- 시작 문서: `Agent Forge - Home.md`
- 전문가 작업장: `notes/`
- 공식 산출물: `docs/`

## 공식 산출물

| 문서 | 목적 |
|---|---|
| [docs/index.md](docs/index.md) | 공식 문서 목차 |
| [docs/project-proposal.md](docs/project-proposal.md) | 회의/상신용 프로젝트 제안서 |
| [docs/use-case-definition.md](docs/use-case-definition.md) | 1차 MVP 유스케이스 정의 |
| [docs/pilot-readiness.md](docs/pilot-readiness.md) | 파일럿 부서/문서/권한 준비 체크리스트 |
| [docs/orchestration-plan.md](docs/orchestration-plan.md) | 오케스트라 운영 계획 |
| [docs/architecture.md](docs/architecture.md) | 전체 아키텍처 |
| [docs/security-model.md](docs/security-model.md) | 사내망 보안 모델 |
| [docs/agent-build-spec.md](docs/agent-build-spec.md) | Agent Build 스펙 |
| [docs/rag-design.md](docs/rag-design.md) | RAG/Data 설계 |
| [docs/implementation-plan.md](docs/implementation-plan.md) | 구현 계획 |
| [docs/implementation-backlog.md](docs/implementation-backlog.md) | 개발 착수용 Epic/Story backlog |
| [docs/evaluation-plan.md](docs/evaluation-plan.md) | 평가 계획 |

## 전문가 역할

- 오케스트라 총괄
- PM Agent
- 수석 아키텍트
- AI 아키텍트
- 보안 아키텍트
- RAG 전문가
- 백엔드 전문가
- 프론트엔드 전문가
- DevOps/MLOps
- QA/Eval

## 현재 기준 결정

- Craft AI는 참고 개념이며, Agent Forge는 사내망용 내부 Agent Builder로 정의합니다.
- 1차 MVP는 사내 문서 기반 RAG 에이전트 빌더입니다.
- DB/ERP/그룹웨어 자동화는 후속 Tool Pack 확장으로 분리합니다.
- MVP의 핵심 검증은 권한 기반 검색, 근거 답변, 실행 로그입니다.
