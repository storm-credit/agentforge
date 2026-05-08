# Agent Forge 프로젝트 개요

## 한 줄 정의

Agent Forge는 사내망 환경에서 승인된 모델, 문서, 도구, 권한정책을 조합해 업무용 AI 에이전트를 생성, 배포, 모니터링하는 사내 Agent Builder 플랫폼이다.

## 왜 필요한가

외부 SaaS형 AI 도구를 그대로 쓰기 어려운 사내망 환경에서는 데이터 반출, 권한 통제, 감사 로그, 시스템 연동 문제가 먼저 해결되어야 한다. Agent Forge는 개별 챗봇을 흩어져 만들지 않고, 표준화된 방식으로 업무용 에이전트를 만들고 운영하기 위한 내부 플랫폼이다.

## 무엇을 만드는가

- Agent Builder: 에이전트 역할, 모델, 문서, 도구, 권한을 설정하는 화면
- Agent Registry: 생성된 에이전트와 버전을 관리하는 저장소
- Model Gateway: 사내 LLM, embedding model, reranker를 연결하는 계층
- Knowledge/RAG: 문서 수집, 파싱, chunking, embedding, 권한 기반 검색
- Tool Registry: 사내 API, DB, 파일서버, 그룹웨어 도구 등록
- Policy Engine: 권한, 승인, 보안 정책 적용
- Runtime Orchestrator: 실제 에이전트 실행 흐름 관리
- Audit Log: 실행 단계, 검색 문서, 도구 호출, 승인 기록 저장

## 1차 MVP

1차 MVP는 사내 문서 기반 RAG 에이전트를 만들 수 있는 Agent Builder로 제한한다. 문서 검색, 권한 필터, 근거 기반 답변, 실행 로그, 기본 에이전트 설정을 검증한다.

## 확장 방향

- DB Readonly Agent
- 그룹웨어 업무 Agent
- ERP 조회/요청 Agent
- 파일서버 검색 Agent
- Git/개발 지원 Agent

