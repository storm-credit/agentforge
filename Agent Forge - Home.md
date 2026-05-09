# Agent Forge - Home

> 사내망 환경에서 승인된 모델, 문서, 도구, 권한정책을 조합해 업무용 AI 에이전트를 만들고 운영하는 사내 Agent Builder 프로젝트.

## 지금 설명할 한 줄

Agent Forge는 Craft AI 같은 에이전트 빌더 개념을 사내망 제약에 맞게 재구성한 통제형 AI 에이전트 제작/운영 플랫폼이다.

## 현재 MVP

- 1차 대상: 사내 문서 기반 RAG 에이전트 빌더
- 핵심 기능: 문서 수집, 권한 기반 검색, 근거 답변, 에이전트 설정, 실행 로그
- 확장 방향: DB 조회, 그룹웨어, ERP, 파일서버, Git/개발 도구 연동

## 빠른 링크

### 오케스트라

- [[notes/00_Orchestrator/오케스트라 총괄 작업지시서|오케스트라 총괄]]
- [[notes/00_Orchestrator/전문가 디스패치 보드|전문가 디스패치 보드]]
- [[notes/00_Orchestrator/오케스트라 실행계획|오케스트라 실행계획]]
- [[notes/00_Orchestrator/오케스트라-에이전트 운영 모델|오케스트라-에이전트 운영 모델]]

### 프로젝트 설명

- [[notes/00_Project/Agent Forge 프로젝트 개요|프로젝트 개요]]
- [[notes/00_Project/MVP 범위|MVP 범위]]
- [[notes/00_Project/프로젝트 제안서 v0.1|프로젝트 제안서 v0.1]]
- [[notes/00_Project/MVP 유스케이스 정의|MVP 유스케이스 정의]]
- [[notes/00_Project/설명 스크립트|설명 스크립트]]

### 전문가 작업장

- [[notes/01_PM/PM Agent 작업지시서|PM Agent]]
- [[notes/02_Architecture/수석 아키텍트 작업지시서|수석 아키텍트]]
- [[notes/03_AI_Runtime/AI 아키텍트 작업지시서|AI 아키텍트]]
- [[notes/04_RAG_Data/RAG 전문가 작업지시서|RAG 전문가]]
- [[notes/05_Security/보안 아키텍트 작업지시서|보안 아키텍트]]
- [[notes/06_Backend/백엔드 전문가 작업지시서|백엔드 전문가]]
- [[notes/07_Frontend/프론트엔드 전문가 작업지시서|프론트엔드 전문가]]
- [[notes/08_DevOps_MLOps/DevOps MLOps 작업지시서|DevOps/MLOps]]
- [[notes/09_QA_Eval/QA Eval 작업지시서|QA/Eval]]
- [[notes/11_Decisions/의사결정 로그|의사결정 로그]]

### 공식 docs

- [공식 문서 목차](docs/index.md)
- [프로젝트 제안서](docs/project-proposal.md)
- [MVP 유스케이스 정의](docs/use-case-definition.md)
- [파일럿 준비](docs/pilot-readiness.md)
- [오케스트라 운영 계획](docs/orchestration-plan.md)
- [오케스트라-에이전트 운영 모델](docs/agent-operating-model.md)
- [딥 전문 에이전트 점검](docs/deep-specialist-audit.md)
- [Open Design 활용 검토](docs/open-design-adoption.md)
- [아키텍처](docs/architecture.md)
- [보안 모델](docs/security-model.md)
- [Agent Build Spec](docs/agent-build-spec.md)
- [RAG 설계](docs/rag-design.md)
- [구현 계획](docs/implementation-plan.md)
- [구현 착수 Backlog](docs/implementation-backlog.md)
- [평가 계획](docs/evaluation-plan.md)

## 이번 주 할 일

- [x] 프로젝트 개요를 1페이지로 확정한다.
- [x] MVP 범위를 문서 에이전트 빌더로 고정한다.
- [x] 문서 등급과 부서 권한 모델 초안을 만든다.
- [x] 에이전트 카드 표준을 확정한다.
- [x] 초기 WBS와 리스크 로그를 채운다.
- [x] 샘플 문서 50~200개 후보 기준을 정한다.
- [ ] 파일럿 부서와 문서 소유자를 지정한다.
- [x] 구현 착수용 backlog를 만든다.
- [x] Sprint 0 착수 범위를 확정한다.
- [x] Sprint 0 API/Web/DB/Compose 골격을 생성한다.
- [x] 오케스트라-전문 에이전트 운영 모델을 명문화한다.
- [x] 전문 에이전트별 D2/D3 깊이 점검을 수행한다.
- [x] 전문가별 D3 증거 seed를 추가한다.
- [x] Open Design 활용 가능성과 경계선을 정리한다.
- [ ] Sprint 0 로컬 실행을 실제 환경에서 검증한다.

## 운영 규칙

- `notes/`는 Obsidian 작업장이다.
- `docs/`는 GitHub에 올릴 공식 산출물이다.
- 초안은 전문가별 폴더에서 작성하고, 합의된 내용만 `docs/`로 승격한다.
- 민감정보, 실제 개인정보, 비공개 문서 원문은 Vault에 직접 붙이지 않는다.
