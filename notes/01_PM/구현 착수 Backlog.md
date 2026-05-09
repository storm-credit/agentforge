# 구현 착수 Backlog

## 문서 목적

이 문서는 Agent Forge MVP를 실제 개발로 전환하기 위한 초기 backlog다. 설계 문서의 내용을 개발 가능한 epic, story, 완료 기준으로 쪼갠다.

## 1. 착수 원칙

- MVP는 문서 기반 RAG Agent Builder만 구현한다.
- ERP, 그룹웨어, 메일, 결재 쓰기 작업은 backlog에 넣지 않는다.
- 권한 필터, citation, audit log는 기능보다 먼저 검증한다.
- 실제 문서가 늦어져도 synthetic corpus와 dummy ACL로 개발을 시작한다.
- 모든 story는 보안/감사 관점의 완료 기준을 포함한다.

## 2. Epic 요약

| Epic | 이름 | 목표 | 우선순위 |
|---|---|---|---|
| EP-00 | 개발 골격 | API/Web/DB/Compose 기본 실행 | P0 |
| EP-01 | Agent Registry | Agent Card와 version/publish 흐름 | P0 |
| EP-02 | Knowledge Ingestion | 문서 업로드, 저장, 색인 job | P0 |
| EP-03 | ACL Retrieval | 권한 기반 검색과 citation 후보 구성 | P0 |
| EP-04 | Runtime Run | 질문, 검색, 답변, trace 저장 | P0 |
| EP-05 | Agent Studio | 관리자 생성/문서/테스트 화면 | P1 |
| EP-06 | Audit/Eval | 감사 로그, golden set, release gate | P1 |
| EP-07 | Closed-net Ops | 폐쇄망 배포, 백업, 관측 | P1 |

## 3. P0 Stories

| ID | Story | 산출물 | 완료 기준 |
|---|---|---|---|
| AF-001 | FastAPI skeleton 생성 | `apps/api` 기본 구조 | `/healthz`, `/readyz`, OpenAPI 생성 |
| AF-002 | Next.js shell 생성 | `apps/web` 기본 구조 | `/agents`, `/knowledge`, `/eval`, `/audit` route 표시 |
| AF-003 | PostgreSQL migration base | Alembic 초기화 | fresh DB migration 성공 |
| AF-004 | Docker compose dev stack | compose 파일 | api, web, postgres, minio, vector store 기동 |
| AF-005 | Agent/Version 테이블 | migration, model | agent 생성과 version 저장 가능 |
| AF-006 | Agent CRUD API | FastAPI endpoints | 목록/생성/수정/상세 contract test |
| AF-007 | Agent version validate/publish | 상태 전이 로직 | published version 단일성 보장 |
| AF-008 | Knowledge source/document 테이블 | migration, model | source/document metadata 저장 |
| AF-009 | MinIO document upload | upload endpoint | 원본 저장, checksum, audit event |
| AF-010 | Index job skeleton | job table, worker stub | queued/running/succeeded/failed 상태 기록 |
| AF-011 | TXT/MD parser smoke | parser module | synthetic 문서 chunk 생성 |
| AF-012 | Embedding/vector adapter interface | interface, fake adapter | contract test 가능 |
| AF-013 | ACL filter model | principal, document_acl | 허용/차단 테스트 데이터 생성 |
| AF-014 | Retrieval preview API | 검색 미리보기 endpoint | 권한 없는 문서가 결과에서 제외됨 |
| AF-015 | Runtime run API skeleton | run/run_step 테이블 | run 생성, 단계 로그 저장 |
| AF-016 | Citation validator | validation module | citation 없는 답변은 failure 처리 가능 |
| AF-017 | Audit event writer | audit service | agent publish, upload, run 이벤트 저장 |
| AF-018 | Synthetic corpus v0.1 | 샘플 문서와 질문 | ACL/citation 테스트 30개 초안 |

## 4. P1 Stories

| ID | Story | 산출물 | 완료 기준 |
|---|---|---|---|
| AF-101 | Agent 목록/상세 UI | Agent Studio 화면 | agent 생성/수정 가능 |
| AF-102 | Builder stepper UI | 설정 단계 UI | 목적, 문서, 모델, 권한, 답변 정책 저장 |
| AF-103 | Knowledge source UI | 문서 관리 화면 | 업로드와 index job 상태 확인 |
| AF-104 | Test Chat UI | 테스트 콘솔 | 답변, citation, run id 표시 |
| AF-105 | Run Trace Viewer | trace 화면 | 검색 문서, 단계, latency 확인 |
| AF-106 | Eval runner | worker/API | golden set 실행과 결과 저장 |
| AF-107 | Eval dashboard | 평가 화면 | pass rate와 실패 case 표시 |
| AF-108 | Audit Explorer | 감사 로그 화면 | 기간/타입/대상 필터 가능 |
| AF-109 | OTel/metrics/logging | 관측 설정 | run_id/trace_id 상관 조회 |
| AF-110 | Offline bundle skeleton | 배포 스크립트 | image/model/checksum manifest 생성 |
| AF-111 | Backup/reindex runbook | 운영 문서 | DB/MinIO/vector 복구 절차 확인 |

## 5. Sprint 0 권장 범위

목표: 개발자가 로컬에서 기본 stack을 띄우고, agent와 document metadata를 저장할 수 있게 만든다.

포함:

- AF-001 FastAPI skeleton
- AF-002 Next.js shell
- AF-003 PostgreSQL migration base
- AF-004 Docker compose dev stack
- AF-005 Agent/Version 테이블
- AF-008 Knowledge source/document 테이블
- AF-017 Audit event writer 초안

제외:

- 실제 LLM 호출
- 실제 임베딩 모델
- SSO 연동
- 복잡한 파일 파서
- 운영용 폐쇄망 bundle

## 6. Sprint 1 권장 범위

목표: synthetic corpus로 문서 업로드, chunk, fake retrieval, run trace까지 연결한다.

포함:

- AF-006 Agent CRUD API
- AF-007 Version validate/publish
- AF-009 MinIO upload
- AF-010 Index job skeleton
- AF-011 TXT/MD parser smoke
- AF-012 Vector adapter interface
- AF-013 ACL filter model
- AF-014 Retrieval preview API
- AF-015 Runtime run API skeleton
- AF-018 Synthetic corpus v0.1

## 7. Sprint 2 권장 범위

목표: 실제 RAG 동작을 최소 수준으로 만들고, 권한 차단과 citation을 검증한다.

포함:

- 실제 embedding adapter 1개
- Qdrant 또는 pgvector adapter 1개
- ACL-aware vector search
- answer generation mock 또는 local model gateway
- citation validator
- Test Chat UI 초안
- Run Trace Viewer 초안
- ACL/citation golden set 실행

## 8. Release Gate

MVP 데모 전 최소 gate:

- agent 생성, version publish, document upload가 UI/API에서 가능
- 권한 없는 문서가 retrieval 후보에 포함되지 않음
- 답변에 citation이 포함됨
- run/run_step/retrieval_hit/audit_event가 저장됨
- golden set에서 ACL suite 100% 통과
- citation 포함률 95% 이상
- 유용 답변 비율 80% 이상 또는 미달 사유가 report에 기록됨

## 9. 오픈 의존성

| 의존성 | 필요 시점 | 막히는 작업 |
|---|---|---|
| 파일럿 부서 선택 | Sprint 0 종료 전 | 실제 문서 후보 확정 |
| 문서 소유자 지정 | Sprint 0 종료 전 | 문서 등급/최신성 검토 |
| 모델/임베딩 가용성 | Sprint 1 중 | 실제 retrieval/generation |
| SSO/권한 원천 | Sprint 1 중 | 운영용 principal/ACL |
| 폐쇄망 배포 환경 | Sprint 2 중 | staging 설치 검증 |
