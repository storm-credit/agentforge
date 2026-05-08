# AI 아키텍트 작업지시서

## 역할

AI 아키텍트는 에이전트 빌드 정의, Runtime Orchestrator, 모델 호출 정책, 프롬프트 정책, 평가 연결 방식을 설계한다.

## 주요 질문

- Agent Build를 어떤 스키마로 정의할 것인가?
- Planner, Retriever, Critic, Security Guard의 경계를 어떻게 나눌 것인가?
- 어떤 단계에서 human approval이 필요한가?
- 모델 변경 시 평가와 배포를 어떻게 통제할 것인가?

## 산출물

- [[notes/03_AI_Runtime/에이전트 빌드 정의|에이전트 빌드 정의]]
- [[notes/03_AI_Runtime/플랫폼 내부 에이전트 목록|플랫폼 내부 에이전트 목록]]
- Prompt policy
- Runtime state schema

