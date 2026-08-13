# AgentForge 사용자·역할·권한 모델 — 실제 코드 기준

Status: 설명용 (파일럿 범위를 정하는 제품 책임자를 위한 문서, 개발자용 소스 안내가 아님)
As of: 2026-08-13 · 근거: `apps/api/app/infra/authz.py`, `apps/api/app/domain/acl.py`,
`apps/api/app/core/principal.py`, `apps/api/app/infra/qdrant_store.py`, `apps/api/app/api/v1/*.py`,
`apps/web/app/lib/demoRole.ts` 등 실제 코드. Line 번호는 위 커밋 시점 기준이며, 병행 작업
(`WO-2026-08-13-CLEARANCE-FAIL-OPEN`)이 `acl.py`를 수정 중이므로 이후 달라질 수 있다 — 내용(코드
동작)을 근거로 삼고, 줄 번호는 참고용으로만 취급할 것.

> **이 문서와 `domain-model.md`의 관계.** `system-walkthrough.md`가 이미 밝힌 대로
> `docs/10-architecture/domain-model.md`는 **의도된 목표 모델**이고 실제 코드에는 없는 엔티티
> (`Build`, `Tool`, `Tool Version`, `Approval Request/Decision`, `Index Snapshot`)를 포함한다.
> 이 문서는 그 반대다 — **오직 지금 코드가 하는 일**만 적는다. 목표 모델과 다른 부분은
> 언급하되 목표 모델 자체를 재서술하지 않는다.

## 0. 한 문장 요약

역할(role)은 세 그룹의 문자열 집합(뮤테이션용 `PRIVILEGED_ROLES`, 감사조회용 `AUDIT_READ_ROLES`,
그리고 코드 여러 곳에 흩어진 리터럴 `"admin"` 체크)으로만 존재하고, 신원은 검증되지 않는 HTTP
헤더에서 온다. 문서 접근은 역할이 아니라 **등급(clearance) × 그룹(access_groups) 교집합**으로
결정되며, 이 결정은 Python과 Qdrant 필터에 **두 번** 구현돼 있다. 데모 화면의 역할 스위처는 이
중 일부만 흉내 낸다.

---

## 1. 역할 어휘 (Role Vocabulary) — 확인된 사실

`apps/api/app/infra/authz.py`가 정의하는 두 역할 집합, **이것이 코드에 존재하는 역할의 전부다**
(그 밖의 "역할"은 리터럴 문자열 비교로 흩어져 있을 뿐 별도 목록으로 선언돼 있지 않다):

```python
# apps/api/app/infra/authz.py:19
PRIVILEGED_ROLES: frozenset[str] = frozenset({"admin", "platform-admin", "knowledge-manager"})

# apps/api/app/infra/authz.py:23
AUDIT_READ_ROLES: frozenset[str] = frozenset({"admin", "platform-admin", "security-auditor"})
```

- `admin`은 **두 집합 모두**에 속한다.
- `platform-admin`도 **두 집합 모두**에 속한다.
- `knowledge-manager`는 뮤테이션 권한만 있고 **감사조회 권한은 없다**(코드 주석 그대로: "a
  knowledge-manager can change ACLs but should not enumerate org-wide who-did-what").
- `security-auditor`는 감사조회 권한만 있고 **뮤테이션 권한은 없다**.
- 이 두 집합 밖의 임의 문자열(예: `developer`, 또는 헤더에 아무것도 안 넣었을 때의 기본값
  `developer`)은 뮤테이션도, 감사조회도 할 수 없다. 역할 문자열에 오탈자를 넣어도 그냥 "권한
  없음"으로 처리된다 — 화이트리스트 방식(존재하는 역할만 통과)이라 이 부분 자체는 안전하다.

### 1-a. `enforce_roles` — 뮤테이션 게이트가 실제로 하는 일

```python
# apps/api/app/infra/authz.py:26-52
def enforce_roles(db, principal, allowed, *, action, target_type="endpoint", target_id=""):
    allowed_set = set(allowed)
    if allowed_set & set(principal.roles):
        return
    write_audit_event(db, principal=principal, event_type="policy.denied", ...)
    db.commit()
    raise HTTPException(status_code=403, detail="Insufficient role for this action")
```

`principal.roles`와 허용 집합의 교집합이 비어있지 않으면 통과, 아니면 **`policy.denied` 감사
이벤트를 기록하고 403**. 거부도 승인도 항상 감사에 남는다.

### 1-b. `enforce_roles` 호출부 전수 — endpoint → 필요 역할 매트릭스

`apps/api` 전체를 grep한 결과, `enforce_roles`를 실제로 **호출하는** 곳은 정확히 13곳이다
(정의부 `authz.py:26`, 각 파일의 `import` 문 4곳, 테스트 파일의 주석 1건, `knowledge.py:120`의
주석 1건은 호출이 아니므로 제외). 아래는 그 13곳 전부다.

| 파일:라인 | 함수 / 라우트 | HTTP | action | 필요 역할 |
|---|---|---|---|---|
| `app/api/v1/agents.py:86` | `update_agent` — `PATCH /agents/{id}` | PATCH | `agent.update` | `PRIVILEGED_ROLES` |
| `app/api/v1/agents.py:121` | `create_agent_version` — `POST /agents/versions` | POST | `agent_version.create` | `PRIVILEGED_ROLES` |
| `app/api/v1/agents.py:194` | `validate_agent_version` — `POST /agents/versions/{id}/validate` | POST | `agent_version.validate` | `PRIVILEGED_ROLES` |
| `app/api/v1/agents.py:224` | `publish_agent_version` — `POST /agents/versions/{id}/publish` | POST | `agent_version.publish` | `PRIVILEGED_ROLES` |
| `app/api/v1/audit.py:31` | `list_audit_events` — `GET /audit/events` | GET | `audit_log.read` | `AUDIT_READ_ROLES` |
| `app/api/v1/eval.py:62` | `create_eval_run` — `POST /eval/runs` | POST | `eval_run.create` | `PRIVILEGED_ROLES` |
| `app/api/v1/knowledge.py:151` | `archive_document` — `DELETE /documents/{id}` | DELETE | `document.archive` | `PRIVILEGED_ROLES` |
| `app/api/v1/knowledge.py:203` | `restore_document` — `POST /documents/{id}/restore` | POST | `document.restore` | `PRIVILEGED_ROLES` |
| `app/api/v1/knowledge.py:262` | `register_document` — `POST /documents` | POST | `document.register` | `PRIVILEGED_ROLES` |
| `app/api/v1/knowledge.py:308` | `update_document_acl` — `PATCH /documents/{id}/acl` | PATCH | `document.acl_update` | `PRIVILEGED_ROLES` |
| `app/api/v1/knowledge.py:402` | `upload_document_and_index` — `POST /documents/upload` | POST | `document.upload` | `PRIVILEGED_ROLES` |
| `app/api/v1/knowledge.py:543` | `create_index_job` — `POST /documents/{id}/index-jobs` (조건부, 아래 참고) | POST | `document.reindex` | `PRIVILEGED_ROLES` |
| `app/api/v1/knowledge.py:631` | `process_index_job` — `POST /index-jobs/{id}/process` (조건부, 아래 참고) | POST | `document.reindex` | `PRIVILEGED_ROLES` |

**조건부 재색인 게이트 (`create_index_job`, `process_index_job`)**: 이 두 곳은 문서가
`has_been_indexed=True`(과거에 한 번이라도 성공적으로 색인된 적이 있는 경우)일 때만
`enforce_roles(PRIVILEGED_ROLES)`를 호출한다. 최초 색인(`has_been_indexed=False`, 실패한
최초 시도 재시도 포함)은 이 게이트를 타지 않고, 대신 아래 1-c의 리터럴 `"admin"` 읽기-ACL
체크만 통과하면 된다. 즉 "문서를 읽을 수 있는 사람은 최초 색인은 할 수 있지만, 이미 신뢰된
콘텐츠가 있는 문서를 재색인(=벡터를 지우고 다시 심는 것)하려면 `PRIVILEGED_ROLES`가
필요하다."

### 1-c. 리터럴 `"admin"` 체크 — `enforce_roles`와 다른 별도의 메커니즘

`enforce_roles`/`PRIVILEGED_ROLES`(3개 역할)와 별개로, **오직 문자열 `"admin"`만** 검사하는
코드가 11곳 있다. 이 두 메커니즘은 **다른 것**이며 혼동하면 안 된다 — `platform-admin`이나
`knowledge-manager` 역할을 가진 사람은 뮤테이션은 할 수 있지만, 아래 목록의 "관리자는 전체를
본다" 우회는 **적용받지 못한다**(리터럴 문자열이 `"admin"`이 아니므로).

| 파일:라인 | 용도 | 효과 |
|---|---|---|
| `agents.py:32` | `list_agents` | non-admin은 `published` 에이전트만 조회 |
| `agents.py:48` | `get_agent` | non-admin이 미공개 에이전트를 조회하면 403이 아니라 **404**(존재 자체를 숨김) |
| `agents.py:164` | `list_agent_versions` | non-admin은 `published`/`superseded` 버전만 |
| `knowledge.py:59` | `list_sources` | non-admin은 등급(clearance) 필터만 적용(그룹/부서 필터는 없음, 2-a 참고) |
| `knowledge.py:113` | `list_documents` | non-admin은 `principal_can_access_document` 통과분만 |
| `knowledge.py:510` | `create_index_job` 읽기-ACL 체크 | non-admin은 문서를 읽을 권한이 없으면 403 |
| `knowledge.py:613` | `process_index_job` 읽기-ACL 체크 | 위와 동일 |
| `knowledge.py:689` | `get_index_job` | non-admin은 문서 읽기 권한 없으면 403 |
| `knowledge.py:708` | `list_document_chunks` | non-admin은 문서 읽기 권한 없으면 403 |
| `runs.py:53` | `_can_read_run` | run의 소유자(`user_id` 일치) 또는 `"admin"`만 읽기 허용 |
| `runs.py:64` | `list_runs` | non-admin은 본인 소유 run만 |

**함의**: "관리자 모드로 전체 시스템을 시연"할 때, 실제로 "전체를 보는" 사람은 정확히
`roles`에 리터럴 `"admin"`을 가진 사람뿐이다. `platform-admin`이나 `knowledge-manager`로는
비공개 에이전트 목록·타인의 run·미공개 지식소스가 안 보인다(문서 뮤테이션은 되지만 조회
바이패스는 안 된다). 이는 코드에 **의도가 명시돼 있지 않은** 비대칭이다 — 왜 뮤테이션 권한
집합(3개 역할)과 조회-전체-바이패스(`"admin"` 1개 역할)가 다른지 설명하는 주석은 없다.

---

## 2. ACL 대상 집합 (ACL Subject Set) — `principal_acl_subjects`

```python
# apps/api/app/domain/acl.py:26-34
def principal_acl_subjects(principal: Principal) -> set[str]:
    subjects = {
        "all-employees",
        f"user:{principal.user_id}",
        f"department:{principal.department}",
    }
    subjects.update(principal.groups)
    subjects.update(f"role:{role}" for role in principal.roles)
    return subjects
```

한 사람이 부여받는 "권한 문자열"은 항상 다음 다섯 종류의 합집합이다:

| 종류 | 예시 | 항상 포함되나 |
|---|---|---|
| 고정 문자열 | `all-employees` | 예 — 모든 principal에 무조건 포함 |
| 사용자 단위 | `user:hr1` | 예 — `user_id` 헤더 값 그대로 |
| 부서 단위 | `department:HR` | 예 — `department` 헤더 값 그대로, 검증 없음 |
| 그룹 | `hr-restricted` | 헤더에 넣은 값만큼 |
| 역할 접두 | `role:admin`, `role:developer` | `roles` 헤더의 각 역할마다 하나씩 |

이 집합이 `document.access_groups`(문자열 리스트)와 **교집합이 하나라도 있으면** 그룹
조건은 통과한다(`bool(subjects.intersection(access_groups))`, `acl.py:52`). 즉 문서의
`access_groups`에 `department:HR`을 넣으면 부서 기반 ACL이, `role:knowledge-manager`를
넣으면 역할 기반 ACL이, `hr-restricted`처럼 임의 문자열을 넣으면 그룹 기반 ACL이 **모두 같은
메커니즘으로** 동작한다 — 스키마상 부서/그룹/역할이 구분된 별도 필드가 아니라 전부 같은
문자열 집합의 원소다.

---

## 3. 전체 접근 결정 — `principal_can_access_document`

```python
# apps/api/app/domain/acl.py:37-52
def principal_can_access_document(principal: Principal, document: Document) -> bool:
    if document.status not in SEARCHABLE_DOCUMENT_STATUSES:          # ① 상태 게이트
        return False
    if document.confidentiality_level in EXCLUDED_INDEX_CONFIDENTIALITY_LEVELS:  # ② 등급 전면 배제
        return False
    if confidentiality_rank(principal.clearance_level) < confidentiality_rank(
        document.confidentiality_level
    ):                                                                # ③ 등급 비교
        return False
    if not document.access_groups:                                   # ④ 빈 그룹 = 아무도 못 봄
        return False
    return bool(principal_acl_subjects(principal).intersection(document.access_groups))  # ⑤ 교집합
```

순서대로 무엇을 거르는가:

1. **상태 게이트** — `document.status`가 `{"registered", "indexed", "ready"}`(=
   `SEARCHABLE_DOCUMENT_STATUSES`)에 없으면 즉시 거부. `archived`, `index_failed` 등은 여기서
   걸린다.
2. **등급 전면 배제** — `confidentiality_level == "confidential"`이면 **등급이나 그룹과
   무관하게** 항상 거부(`EXCLUDED_INDEX_CONFIDENTIALITY_LEVELS = {"confidential"}`). 즉
   `confidential`은 이 코드 경로 전체에서 아무도 검색/열람할 수 없다 — 등록은 가능하지만
   list/access 판정에서는 항상 걸러진다는 뜻.
3. **등급 비교(clearance rank)** — principal의 등급 랭크가 문서 등급 랭크보다 **낮으면** 거부.
   같거나 높으면 통과(즉 `internal` principal은 `internal`·`public` 문서를 통과, `restricted`
   문서는 거부).
4. **빈 access_groups** — 문서에 `access_groups`가 비어 있으면 무조건 거부(deny-by-default).
5. **교집합** — §2의 principal 대상 집합과 문서 `access_groups`가 하나라도 겹쳐야 최종 허용.

**이 판정은 두 번 구현돼 있다** — Python(`acl.py`, list/개별 조회 경로에서 사용)과 Qdrant
쿼리 필터(`app/infra/qdrant_store.py`, 벡터 검색 경로에서 사용). 두 구현이 논리적으로
일치하는지 확인한 결과:

| 조건 | Python (`acl.py`) | Qdrant (`qdrant_store.py`) | 일치 여부 |
|---|---|---|---|
| 상태 게이트 | `status in {registered, indexed, ready}` | `status == "indexed"`만 허용(`build_qdrant_acl_filter:39`, `payload_allows:61`) | **더 엄격함, 의도적** — 코드 주석: "Only fully-indexed documents are surfaced via vector search...payload_allows mirrors the filter, not the broader domain ACL"(`qdrant_store.py:21-24`). 검색 결과는 항상 색인 완료본만, 리스트 조회는 등록/준비 상태도 보여준다는 뜻으로 둘 다 "권한 없는 것을 보여준다"는 결함은 아니다. |
| 등급 전면 배제 | `confidential` 배제 | `level_rank >= confidentiality_rank("confidential")` 배제(`payload_allows:67`) | 일치 |
| 등급 비교 | `clearance_rank < doc_rank` → 거부 | Qdrant 쿼리 필터는 `range=lte(clearance)`(즉 `doc_rank <= clearance_rank`만 통과, `qdrant_store.py:40`); `payload_allows`는 `level_rank > clearance_rank` → 거부(`qdrant_store.py:71`) | 일치(부등식 방향이 같은 조건의 다른 표현) |
| 빈 그룹 | `not access_groups` → 거부 | `not groups` → 거부(`payload_allows:76`) | 일치 |
| 교집합 | `set.intersection` | `set(groups).intersection(subjects)`(`payload_allows:79`), 쿼리 단계에서는 `MatchAny`(`qdrant_store.py:41`) | 일치 |

Qdrant 경로에는 **두 겹의 방어**가 있다: 쿼리 자체를 필터링하는 `build_qdrant_acl_filter`(검색
전 단계)와, 반환된 각 포인트를 다시 검사하는 `payload_allows`(방어적 재확인, "낡은 색인 등으로
필터를 뚫고 나온 포인트가 있어도 다시 거부"). 코드 주석이 이를 "defense-in-depth"로 명시한다.

**결론**: 두 구현은 일치한다(등급 방향은 `confidentiality_rank()` 함수 하나를 공유하므로
당연히 같은 결과를 낸다). 단, `confidentiality_rank()` 자체에 §7의 결함이 있어 **양쪽 다** 같은
결함을 그대로 물려받는다.

---

## 4. 신원의 출처 — `get_principal`

```python
# apps/api/app/core/principal.py:15-30
def get_principal(
    user_id: str = Header(default="local-user", alias="X-Agent-Forge-User"),
    department: str = Header(default="Sandbox", alias="X-Agent-Forge-Department"),
    roles: str = Header(default="developer", alias="X-Agent-Forge-Roles"),
    groups: str = Header(default="all-employees", alias="X-Agent-Forge-Groups"),
    clearance_level: str = Header(default="internal", alias="X-Agent-Forge-Clearance"),
) -> Principal:
    ...
```

| 헤더 | 기본값(헤더 없을 때) | 의미 |
|---|---|---|
| `X-Agent-Forge-User` | `local-user` | 신원 검증 없음. 어떤 문자열이든 그대로 `user_id`가 된다. |
| `X-Agent-Forge-Department` | `Sandbox` | 자유 문자열. `department:{value}` ACL 대상이 된다. |
| `X-Agent-Forge-Roles` | **`developer`** | 콤마 구분 문자열. `developer`는 `PRIVILEGED_ROLES`/`AUDIT_READ_ROLES` 어디에도 없으므로 **아무 권한도 없는 기본값**이다. |
| `X-Agent-Forge-Groups` | `all-employees` | 콤마 구분. 헤더를 안 보내도 이미 `principal_acl_subjects`가 `all-employees`를 자동 포함하므로 사실상 중복. |
| `X-Agent-Forge-Clearance` | `internal` | 자유 문자열, 소문자 변환 외 검증 없음(§7 참고). |

**헤더를 아무것도 안 보내면** — 즉 어떤 클라이언트든 인증 헤더 없이 API를 호출하면 —
`user_id=local-user, department=Sandbox, roles=(developer,), groups=(all-employees,),
clearance=internal`로 해석된다. 이는 **뮤테이션도 감사조회도 못 하지만, `internal` 등급
이하이고 `all-employees` 그룹에 속한 문서는 읽을 수 있는** principal이다. 신원 위조 방지
장치는 전혀 없다 — 이는 ADR-103(SSO 미연동)이 이미 기록한 알려진 한계이며, 아래 §7-b에서
다시 분명히 짚는다.

---

## 5. 데모 역할 스위처 대 실제 역할 — 명확히 구분

`apps/web/app/lib/demoRole.ts`가 정의하는 화면상의 역할 4개:

```typescript
// apps/web/app/lib/demoRole.ts:10-61
DEMO_ROLES = { admin, developer, finance, hr }
```

| 데모 역할 | 보내는 `X-Agent-Forge-Roles` | 보내는 `X-Agent-Forge-Groups` | 보내는 Clearance |
|---|---|---|---|
| `admin` | `admin` | `all-employees` | `internal` |
| `developer` | `developer` | `all-employees` | `internal` |
| `finance` | `developer` | `all-employees` | `internal` |
| `hr` | `developer` | `all-employees,hr-restricted` | `restricted` |

**여기서 확인한 사실 (사용자가 미리 알려준 내용과 정확히 일치)**: 백엔드의 뮤테이션 역할
어휘는 `admin` / `platform-admin` / `knowledge-manager`(`PRIVILEGED_ROLES`), 감사조회 어휘는
`admin` / `platform-admin` / `security-auditor`(`AUDIT_READ_ROLES`)이다. 프런트엔드
`DEMO_ROLES`가 실제로 `X-Agent-Forge-Roles` 헤더에 넣는 값은 `admin`과 `developer` **단 두
가지뿐**이다(`finance`/`hr` 데모 역할도 roles 헤더로는 `developer`를 보낸다 — 이름은
"finance"/"hr"이지만 그것은 `department`/`groups`/`clearance`를 바꾸는 것이지 `roles`를
바꾸는 것이 아니다). **`platform-admin`, `knowledge-manager`, `security-auditor`는 이 UI에서
전혀 만들어낼 수 없다** — `demoRole.ts`를 처음부터 끝까지 읽어도 이 세 문자열은 등장하지
않는다(코드에 존재하지 않음, grep 결과 0건).

`isPrivilegedDemoRole`(`demoRole.ts:83-85`)도 `PRIVILEGED_DEMO_ROLES = new Set(["admin"])`
하나만 담고 있고, 그 옆의 주석이 이유를 명시한다: "developer/finance/hr all send
roles=\"developer\", which the backend does not treat as privileged, so listing any of them
here would make the UI advertise authority the server refuses." — 즉 UI 작성자도 이 셋의
구현체가 없다는 것을 알고 의도적으로 그렇게 둔 것이다.

**실증 가능한 것과 아닌 것**:

| 역할 | 실증 가능? | 근거 |
|---|---|---|
| `admin`(뮤테이션+감사조회 겸용, 조회-전체-바이패스도 겸용) | **가능** | `demoRole.ts`의 `admin` 스위처 |
| `developer`(무권한 기본 사용자) | **가능** | `demoRole.ts`의 `developer` 스위처, 그리고 `finance`/`hr`도 실제로는 이 역할 |
| 그룹 기반 ACL(등급 없이 그룹만으로 문서를 보이게/안 보이게) | **가능** | `demoRole.ts`의 `hr` 스위처(`hr-restricted` 그룹 + `restricted` 등급) |
| `platform-admin` | **불가능** | UI에 해당 역할을 보내는 스위처가 없음(백엔드 API에는 헤더로 직접 보내면 동작함 — UI 경유만 불가능) |
| `knowledge-manager` | **불가능** | 위와 동일 |
| `security-auditor` | **불가능** | 위와 동일 |

**이것이 의미하는 바 (제품 책임자를 위해 명확히 진술)**: "시스템 관리자 모드로 전체를
시연"한다고 할 때, 화면으로 보여줄 수 있는 것은 사실상 **딱 한 종류의 관리자
경험**(`admin` = 뮤테이션+감사조회+조회-전체-바이패스를 모두 가진 단일 역할)뿐이다.
실제 코드가 구분해 놓은 "지식 관리자(문서/ACL 편집은 되지만 감사조회는 안 됨)"나
"보안 감사자(감사조회는 되지만 문서 편집은 안 됨)"처럼 **권한을 쪼갠 역할 분리**는
서버에서는 동작하지만(적절한 헤더를 curl/Postman 등으로 직접 보내면 확인 가능),
**UI를 통한 데모로는 보여줄 수 없다**. 파일럿을 "관리자 모드"로 규정할 때, 그 관리자가
`admin` 하나의 슈퍼롤을 의미하는지, 아니면 실제 존재하는 세 가지 분리된 역할(지식관리자/
보안감사자/플랫폼관리자)을 의미하는지는 **이 문서가 대신 정할 수 없는 결정**이다.

---

## 6. `owner_department` — 권한 입력이 아니다

`owner_department`는 `KnowledgeSource`(`app/domain/models.py:25`)와 `Agent`
(`app/domain/models.py:63`)에 모두 존재하는 필수 문자열 컬럼이다. **`app/domain/acl.py`
전체를 grep한 결과 `owner_department`는 단 한 번도 등장하지 않는다** — 즉 이 필드는
`principal_acl_subjects`에도, `principal_can_access_document`에도, Qdrant 필터에도
**전혀 읽히지 않는다**. 확인된 사실:

- 값은 생성/수정 시 그대로 저장되고(`app/api/v1/knowledge.py:98`, `agents.py:68`의 감사
  페이로드), 화면에 표시되고(`apps/web/app/agents/page.tsx:28`, `apps/web/app/agents/[id]/page.tsx:97`)
  끝난다 — 접근 판정에는 관여하지 않는다.
- 프런트엔드 지식소스 생성 폼은 이 값을 **하드코딩**한다:
  `apps/web/app/knowledge/page.tsx:163` — `owner_department: "Operations"`. 즉 지금
  UI로 만든 모든 지식소스는 실제 생성자가 누구든 항상 `owner_department="Operations"`로
  기록된다 — 이는 현재 **틀린 데이터**다(생성자의 실제 부서를 반영하지 않음). 참고로 에이전트
  생성 폼(`apps/web/app/agents/new/page.tsx:62`)은 사용자가 입력한 `department` 값을 쓰고,
  비어 있을 때만 `"Operations"`로 대체한다 — 지식소스 쪽과 다른 처리다.

**왜 이것을 명시적으로 짚는가**: 이름이 `owner_department`이고 `document.access_groups`에
`department:{value}` 같은 문자열을 넣을 수 있는 구조가 이미 있기 때문에, 읽는 사람은 자연히
"부서 소유자 필드가 접근을 제한하겠구나"라고 가정하기 쉽다. 지금은 그렇지 않다. 하지만
이것은 **부서 기반 분류 규칙(예: "이 지식소스는 소유 부서만 볼 수 있다")을 추가하는 순간
그대로 권한 입력이 되는 필드**다 — 스키마가 이미 있고, 필수값이고, 매 지식소스/에이전트에
채워져 있으니 규칙 하나만 `acl.py`에 추가하면 즉시 작동한다. 부서 기반 분류를 설계할 때는 이
필드가 지금 하드코딩된 잘못된 값("Operations")으로 채워져 있다는 사실을 먼저 정리해야 한다.

---

## 7. 이 모델의 알려진 결함 — 기록만, 수정하지 않음

### 7-a. Clearance 등급 해석의 fail-open (수정 진행 중, 이 문서는 손대지 않음)

```python
# apps/api/app/domain/acl.py:22-23
def confidentiality_rank(level: str) -> int:
    return CONFIDENTIALITY_RANK.get(level.lower(), CONFIDENTIALITY_RANK["confidential"])
```

이 함수는 **문서 등급과 principal 등급 양쪽에 동일하게** 적용된다(`principal_can_access_document`의
③번 비교, §3 참고). 미인식 값을 최고 랭크(`confidential`=3)로 매핑하는 것은:

- **문서(object) 쪽에서는 fail-closed가 맞다** — 등급을 알 수 없는 문서는 가장 민감하게
  취급해서 아무나 못 보게 하는 것이 안전한 방향이다. 게다가 문서 등급은 매 쓰기마다
  `_validate_confidentiality`(`app/api/v1/knowledge.py`)로 **검증된다** — 알 수 없는 값은
  애초에 저장되지 않는다.
- **principal(subject) 쪽에서는 fail-open이다** — principal의 clearance는 **어디서도
  검증되지 않고**, `X-Agent-Forge-Clearance` 헤더 값이 그대로
  `confidentiality_rank()`에 들어간다. 오탈자·공백·빈 문자열이 들어오면 "가장 민감한
  문서까지 볼 수 있는 사람"으로 해석돼버린다.

**실측 재현(제품 책임자가 2026-08-13에 직접 재현, 이 문서 작성자는 코드 경로만 확인했고
라이브 재현은 하지 않음)**: 동일한 사용자·그룹으로 `X-Agent-Forge-Clearance` 헤더만 바꿔가며
`internal` → 정상적으로 `restricted` 문서를 걸러냄, `internal `(끝에 공백 1개) / `typo-xyz` /
`""`(빈 문자열) → 각각 `internal`이 걸러내는 `restricted` 문서를 노출.

이 결함은 **`WO-2026-08-13-CLEARANCE-FAIL-OPEN`**(`harness/work-orders/WO-2026-08-13-CLEARANCE-FAIL-OPEN.yaml`,
상태 `accepted`, 담당 `security-trust-architect`) 아래 별도 에이전트가 지금 수정 중이다. 이
Work Order의 범위는 subject 쪽 등급 해석을 fail-closed로 바꾸는 것(알 수 없는/공백/빈 값 →
최저 랭크)이며, object 쪽 동작과 그룹/역할 평가는 건드리지 않는다. **이 문서는 `acl.py`를
수정하지 않는다** — 위 서술은 결함의 기록일 뿐이며, 수정 완료 여부는 위 Work Order의 상태를
확인해야 한다.

참고로 이 결함의 영향 범위(WO 본문이 명시)는 오늘 기준 제한적이다 — `confidential`은 전역
배제이고 그룹 교집합 조건은 여전히 적용되므로, 실제로 노출되는 것은 "그 principal이 그룹
조건은 이미 만족하는 `restricted` 등급 자료"까지다. 다만 ADR-103(SSO 연동)이 진행되면 IdP가
공급하는 등급 클레임 값 하나가 매핑에서 누락되는 것만으로 그 값을 가진 모든 principal이
동시에 등급이 상승하는 경로이므로, 지금 고치는 것이 맞다.

### 7-b. 신원이 검증되지 않은 헤더 스텁이다 (ADR-103, `OPEN`)

§4에서 확인했듯 `Principal`은 서명되지 않은 HTTP 헤더에서 그대로 만들어진다. 이것이 의미하는
바를 한 번만 분명히 진술한다: **서버 측 역할/ACL 강제 로직 자체는 실제로 동작한다** — 이
문서의 §1~3이 기술한 게이트는 전부 실제 코드고 실제로 그 조건대로 걸러낸다. 그러나 "누가
그 역할을 주장하는가"를 검증하는 계층이 없으므로, **작정하고 헤더를 조작하는 공격자에게는
이 강제가 신뢰할 수 없다**. 이것은 과장해서도, 축소해서도 안 된다 — 강제 로직의 정확성과
신원의 신뢰성은 별개 축이고, 전자는 확인됐고 후자는 미해결(ADR-103 `OPEN`)이다.

---

## 8. 역할×기능 매트릭스 — 요약

읽는 사람이 한눈에 스캔할 수 있도록: `PRIVILEGED_ROLES` = P, `AUDIT_READ_ROLES` = A,
리터럴 `"admin"` 전체조회 = ★, 그 외 모두 = 없음(계정 소유 데이터/ACL 통과분만).

| 기능 | admin | platform-admin | knowledge-manager | security-auditor | 그 외(예: developer) |
|---|:---:|:---:|:---:|:---:|:---:|
| 에이전트 생성/수정/버전관리/검증/발행 | O (P) | O (P) | O (P) | X | X |
| 문서 등록/업로드/ACL수정/보관/복원/재색인 | O (P) | O (P) | O (P) | X | X |
| 최초 색인(문서를 읽을 수 있는 principal만) | O | O | O | O(읽기ACL 통과 시) | O(읽기ACL 통과 시) |
| Eval 결과 기록 | O (P) | O (P) | O (P) | X | X |
| 감사 로그 조회(`GET /audit/events`) | O (A) | O (A) | X | O (A) | X |
| 미공개 에이전트/전체 문서/타인 run 조회(★) | O | X | X | X | X |
| 본인 소유 run 조회 | O | O | O | O | O |
| 등급·그룹 조건을 만족하는 문서 검색/열람 | O | O | O | O | O(조건 만족 시) |

읽는 법: `knowledge-manager`는 문서/에이전트를 바꿀 수 있지만 감사 로그는 못 보고, 미공개
에이전트 목록이나 타인의 run도 못 본다(★ 칸이 `admin`에만 O). `security-auditor`는 그
반대다. 이 넷 중 UI로 실제로 눌러볼 수 있는 것은 `admin`과 "그 외"뿐이다(§5).

---

## 9. 지금 없는 것 (Absent) — 목표 모델을 지어내지 않고 사실만 기록

- **셀프서비스 역할 신청**이 없다. 역할은 헤더 값이고, 누가 어떤 역할을 받을 수 있는지
  결정/승인하는 흐름이 코드에 없다.
- **위임(delegation)**이 없다. 관리자가 특정 리소스에 한해 일시적으로 권한을 넘기는
  메커니즘이 없다.
- **`PRIVILEGED_ROLES` 3개 / `AUDIT_READ_ROLES` 3개** 외의 직무 분리(separation of duties)가
  없다 — 예를 들어 "문서를 등록한 사람과 발행을 승인하는 사람이 달라야 한다" 같은 4-eyes
  규칙은 구현돼 있지 않다(같은 `knowledge-manager`가 등록도 발행도 다 할 수 있다).
  `docs/30-decisions/adr-register.md`의 `ADR-113`(파일럿 릴리스 승인자·직무분리)이 이를
  아직 `OPEN`으로 남겨둔 것과 일치한다.
- **"시스템 관리자 모드"가 운영적으로 무엇을 의미하는지 정의한 문서가 없다.** 이 저장소
  어디에도 "관리자 모드 파일럿"이 구체적으로 어떤 역할 조합, 어떤 데이터 범위, 어떤 운영
  통제를 뜻하는지 정의한 문서가 없다 — 지금 코드가 가진 것은 §1~8에 적은 개별 게이트뿐이고,
  그것들을 하나의 "운영 모드" 개념으로 묶는 상위 정의는 존재하지 않는다.
