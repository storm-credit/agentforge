# 권한 ACL Matrix

## 목적

이 문서는 Agent Forge MVP의 접근제어 기준을 정의한다. 접근제어는 사용자 인증, 에이전트 접근 권한, 문서 ACL, 도구 호출 권한, 감사 로그 조회 권한을 분리해서 판정한다.

기본 원칙은 deny-by-default이다. 명시적으로 허용되지 않은 사용자, 문서, 에이전트, 도구 조합은 실행할 수 없다.

## 권한 판정 입력

| 권한 축 | 설명 | MVP 처리 | 기준 시스템/출처 | 비고 |
|---|---|---|---|---|
| user_id | 사용자 고유 식별자 | 필수 | AD/LDAP/OIDC | 실행 로그와 연결 |
| department_id | 소속 부서 | 필수 | IAM 또는 HR master | 문서 검색 필터 |
| role | 업무 역할 또는 플랫폼 역할 | 필수 | IAM group 또는 Agent Forge role | 관리자/소유자/사용자 구분 |
| security_group | 보안 그룹 | 선택 | IAM group | 제한/기밀 문서 접근에 사용 |
| employment_status | 재직/휴직/퇴사 상태 | 필수 | IAM 또는 HR master | 비활성 계정 차단 |
| agent_id | 호출 대상 에이전트 | 필수 | Agent Registry | 에이전트별 허용 사용자 검증 |
| document_id | 원본 문서 식별자 | 필수 | Document Store | citation과 감사 추적 |
| confidentiality_level | 문서 등급 | 필수 | Metadata Store | 공개/내부/제한/기밀 |
| owner_department_id | 문서 소유 부서 | 필수 | Metadata Store | 부서 기반 열람 통제 |
| allowed_subjects | 허용 사용자/부서/그룹 | 필수 | ACL Store | 검색 전 filter |
| project_scope | 프로젝트 범위 | 이후 | Project master | 부서 간 프로젝트용 |
| purpose | 실행 목적 | 이후 | 요청 파라미터/승인 워크플로 | 목적 기반 접근제어 |

## 플랫폼 역할

| 역할 | 설명 | 대표 권한 | 금지 사항 |
|---|---|---|---|
| Platform Admin | 플랫폼 설치, 모델/도구/정책 운영 담당 | 시스템 설정, 모델 카탈로그, Tool Registry 관리 | 감사 로그 임의 수정, 문서 ACL 우회 |
| Security Auditor | 보안 검토 및 감사 담당 | 감사 로그 조회, 정책 위반 이벤트 조회 | 에이전트 실행 결과 원문 임의 열람 |
| Agent Owner | 특정 에이전트 생성/운영 담당 | 에이전트 설정, 문서 범위 요청, 테스트 실행 | 승인 없는 배포, 타 소유 에이전트 변경 |
| Knowledge Manager | 문서 수집/메타데이터 관리 담당 | 문서 등록, 등급/소유자/보존기간 입력 | 권한 없는 문서 등급 완화 |
| End User | 업무 질의 사용자 | 허용 에이전트 실행, 본인 실행 이력 조회 | 타인 로그 조회, 도구 직접 호출 |
| Service Account | 시스템 내부 작업 계정 | ingestion, embedding, scheduled job | 대화형 로그인, 범위 밖 API 호출 |
| Tool Pack Developer | 확장 도구 개발 담당 | 개발 환경에서 도구 스키마 제안 | 운영 Tool Registry 직접 활성화 |

## 리소스별 ACL Matrix

| 리소스/행위 | Platform Admin | Security Auditor | Agent Owner | Knowledge Manager | End User | Service Account |
|---|---|---|---|---|---|---|
| 에이전트 정의 조회 | 전체 | 감사 목적 전체 | 소유 에이전트 | 문서 연결 범위만 | 허용 에이전트 요약 | 필요 범위 |
| 에이전트 생성/수정 | 가능 | 불가 | 가능 | 불가 | 불가 | 불가 |
| 에이전트 배포 | 정책 충족 시 가능 | 불가 | 승인 요청 | 불가 | 불가 | 배포 작업 실행만 |
| 모델 선택/변경 | 가능 | 조회 | 소유 에이전트 후보 선택 | 불가 | 불가 | 불가 |
| Tool Registry 변경 | 가능 | 조회 | 도구 사용 요청 | 불가 | 불가 | 불가 |
| 문서 등록 | 설정 가능 | 조회 | 연결 요청 | 가능 | 불가 | ingestion 실행 |
| 문서 ACL 변경 | 정책 관리 가능 | 조회 | 요청 | 메타데이터 수정 가능 | 불가 | 동기화 실행 |
| 문서 원문 조회 | 권한 있는 문서만 | 원칙적으로 불가 | 권한 있는 문서만 | 권한 있는 문서만 | 권한 있는 문서만 | ingestion 범위 |
| 문서 검색 실행 | 테스트 목적 가능 | 제한적 재현 | 소유 에이전트 테스트 | 검수 목적 가능 | 허용 에이전트만 | 불가 |
| 일반 실행 로그 조회 | 운영 목적 전체 | 감사 목적 전체 | 소유 에이전트 | 문서 처리 로그 | 본인 로그 | 작업 로그 |
| 감사 로그 조회 | 제한적 가능 | 가능 | 소유 에이전트 일부 | 문서 ingestion 일부 | 불가 | 불가 |
| 감사 로그 수정/삭제 | 불가 | 불가 | 불가 | 불가 | 불가 | 불가 |
| 정책 위반 해제 | 승인 절차 필요 | 승인 의견 | 요청 | 요청 | 불가 | 불가 |

## 문서 등급 정책

| 등급 | 설명 | MVP 정책 | 검색/응답 처리 |
|---|---|---|---|
| 공개 | 전 임직원 열람 가능 | 검색 가능 | citation 포함 가능 |
| 내부 | 사내 구성원 열람 가능 | 검색 가능 | 사용자 재직 상태 확인 |
| 제한 | 특정 부서/역할/그룹만 열람 가능 | ACL 필수 | 검색 전 filter와 응답 전 재검증 |
| 기밀 | 제한된 사용자만 열람 가능하고 유출 영향이 큰 문서 | MVP 기본 제외 | 별도 승인, 마스킹, break-glass 필요 |

기밀 문서는 MVP에서 기본 색인 대상이 아니다. PoC 또는 통제된 파일럿에서 다루려면 별도 보안 승인, 전용 index, 더 짧은 보존 기간, 원문 미노출 정책을 요구한다.

## 문서 ACL 모델

문서 ACL은 다음 구조를 기준으로 한다.

```yaml
document_acl:
  document_id: "doc-001"
  confidentiality_level: "restricted"
  owner_department_id: "finance"
  allowed_users: ["u123"]
  allowed_departments: ["finance"]
  allowed_groups: ["finance-managers"]
  denied_users: []
  retention_policy: "3y"
  source_system: "file-share"
  last_synced_at: "2026-05-09T00:00:00+09:00"
```

### ACL 평가 순서

1. 사용자 인증 상태와 계정 활성 상태를 확인한다.
2. 에이전트 실행 권한을 확인한다.
3. 에이전트에 연결된 문서 scope를 확인한다.
4. 문서의 deny rule을 먼저 평가한다.
5. allowed_users, allowed_departments, allowed_groups 중 하나 이상 일치하는지 확인한다.
6. confidentiality_level에 따른 추가 조건을 확인한다.
7. 검색 결과 chunk별 document_id와 ACL을 응답 직전에 재검증한다.

## Runtime 권한 적용 지점

```mermaid
flowchart LR
  REQ["사용자 요청"] --> AUTH["인증/계정 상태"]
  AUTH --> AG["에이전트 실행 권한"]
  AG --> POL["정책 판정"]
  POL --> RET["검색 전 ACL filter"]
  RET --> RERANK["Rerank"]
  RERANK --> POST["검색 후 ACL 재검증"]
  POST --> GEN["답변 생성"]
  GEN --> OUT["출력 guard/masking"]
  OUT --> AUD["감사 로그"]
```

## 캐시와 권한 회수

- 사용자 권한, 부서, 그룹 정보는 짧은 TTL로 캐시할 수 있다.
- 권한 회수, 퇴사, 부서 이동 이벤트는 캐시 무효화 대상이다.
- 문서 ACL 변경 시 관련 vector index metadata와 retrieval cache를 무효화한다.
- 응답 캐시는 사용자/에이전트/ACL version을 key에 포함해야 한다.
- ACL version이 다르면 이전 cache를 재사용하지 않는다.

## MVP와 이후 확장

| 항목 | MVP | 이후 확장 |
|---|---|---|
| 사용자 인증 | AD/LDAP/OIDC 중 하나와 연동하는 추상 Identity Provider | SSO 세션 정책, step-up auth |
| 문서 ACL | 부서/사용자/그룹/등급 기반 | 프로젝트, 목적, 시간, 위치 조건 |
| 도구 ACL | 읽기/검색 도구만 허용 | DB/ERP/그룹웨어별 세부 action ACL |
| 승인 정책 | 고위험 변경 기록 중심 | 다단계 승인, break-glass, SoD |
| 정책 언어 | 테이블 기반 정책 | ABAC/Rego 등 정책 엔진 검토 |

