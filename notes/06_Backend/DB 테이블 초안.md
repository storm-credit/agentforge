# DB 테이블 초안

| 테이블 | 목적 |
|---|---|
| agents | 에이전트 기본 정보 |
| agent_versions | 프롬프트, 모델, 도구, 정책 버전 |
| tools | 등록된 사내 도구/API |
| tool_permissions | 도구별 사용 권한 |
| knowledge_sources | 문서 저장소, DB, 파일서버 소스 |
| documents | 문서 메타데이터 |
| document_chunks | RAG chunk 메타데이터 |
| document_acl | 문서별 사용자/부서 권한 |
| runs | 에이전트 실행 단위 |
| run_steps | planner/retriever/tool/verifier 단계 로그 |
| tool_calls | 도구 호출 기록 |
| approvals | human-in-the-loop 승인 기록 |
| eval_cases | 평가셋 |
| eval_results | 평가 결과 |
| audit_events | 보안/운영 감사 이벤트 |

