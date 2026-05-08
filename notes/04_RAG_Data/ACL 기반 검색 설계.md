# ACL 기반 검색 설계

## 원칙

권한 필터는 검색 이후가 아니라 검색 조건 단계에서 먼저 적용한다. 사용자가 볼 수 없는 문서는 LLM 컨텍스트에 들어가면 안 된다.

## 권한 축

- user_id
- department_id
- role
- document_level
- project_scope

## 검색 단계

1. 사용자 권한 컨텍스트 생성
2. query embedding 생성
3. vector search에 ACL payload filter 적용
4. 후보 chunk rerank
5. citation 가능한 chunk만 답변 컨텍스트로 전달
6. 출력 전 Security Guard 재검사

