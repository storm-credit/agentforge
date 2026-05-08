# DevOps MLOps 작업지시서

## 역할

DevOps/MLOps는 폐쇄망 배포, 모델 서빙, 로그/모니터링, 백업, 인덱스 재생성 절차를 설계한다.

## 주요 질문

- 모델은 vLLM, Ollama, 또는 기존 사내 모델 서버 중 무엇을 쓸 것인가?
- GPU 서버와 API 서버는 분리되는가?
- Vector DB는 Qdrant인가, PostgreSQL pgvector인가?
- 폐쇄망에서 패키지와 모델 파일은 어떻게 반입하고 검증하는가?

## 산출물

- [[notes/08_DevOps_MLOps/폐쇄망 배포 구상|폐쇄망 배포 구상]]
- 운영 runbook
- 모니터링 지표

