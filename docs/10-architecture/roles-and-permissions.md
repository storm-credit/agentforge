# AgentForge 사용자·역할·권한 모델 — 실제 코드 기준

Status: 설명용 (파일럿 범위를 정하는 제품 책임자를 위한 문서, 개발자용 소스 안내가 아님)
As of: 2026-08-13 · 근거: `apps/api/app/infra/authz.py`, `apps/api/app/domain/acl.py`,
`apps/api/app/core/principal.py`, `apps/api/app/infra/qdrant_store.py`, `apps/api/app/api/v1/*.py`,
`apps/web/app/lib/demoRole.ts` 등 실제 코드. Line 번호는 위 커밋 시점 기준이며 병행 작업으로
달라질 수 있다 — 내용(코드 동작)을 근거로 삼고, 줄 번호는 참고용으로만 취급할 것. §1-c와 §3, §8은
`WO-2026-08-13-ROLE-READ-COHERENCE`로 2026-08-13에 갱신됐고(그 과정에서 줄 번호 참조는 함수명
참조로 바꿨다), §7-a의 clearance fail-open 항목은 별도 Work Order 소관이므로 그대로 두었다.
**§10은 `WO-2026-08-13-MUTATION-GATE-SWEEP`가 추가한 상태변경 엔드포인트 인가 인벤토리다** —
§1-b(호출부 전수)와 §8(역할×기능 요약)도 그때 함께 정정됐다(§8의 "에이전트 생성" 행은 코드와
달랐다, §10-b 참고). §10의 표는 **테스트로 강제된다**: 결정이 기록되지 않은 상태변경 라우트가
있으면 `apps/api/tests/test_route_authorization_inventory.py`가 실패한다.

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

> **2026-08-13 갱신 (`WO-2026-08-13-ROLE-READ-COHERENCE`).** 이 문서 초판은 "뮤테이션 권한
> 3역할 vs 조회 바이패스 1역할(`admin`)"의 비대칭을 **현재 상태로 기록**했다. 그 비대칭 중
> "부여된 뮤테이션을 수행하기 위해 반드시 필요한 조회(discovery)" 부분은 이제 해소됐고, 문서도
> 그에 맞춰 갱신했다. **해소되지 않은(=의도적으로 유지한) 부분**은 일반 ACL 바이패스로, 여전히
> 리터럴 `"admin"` 전용이다. 두 가지를 구분해서 읽을 것 — §1-c의 분류 열이 그 구분이다.

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

`apps/api` 전체를 grep한 결과, `enforce_roles`를 실제로 **호출하는** 곳은 정확히 14곳이다
(정의부 `authz.py:26`, 각 파일의 `import` 문 4곳, 테스트 파일의 주석 1건, `knowledge.py:120`의
주석 1건은 호출이 아니므로 제외). 아래는 그 14곳 전부다. 초판 기준으로는 13곳이었고,
`create_source`가 `WO-2026-08-13-MUTATION-GATE-SWEEP`에서 추가돼 14곳이 됐다.

| 파일:라인 | 함수 / 라우트 | HTTP | action | 필요 역할 |
|---|---|---|---|---|
| `app/api/v1/agents.py:86` | `update_agent` — `PATCH /agents/{id}` | PATCH | `agent.update` | `PRIVILEGED_ROLES` |
| `app/api/v1/agents.py:121` | `create_agent_version` — `POST /agents/versions` | POST | `agent_version.create` | `PRIVILEGED_ROLES` |
| `app/api/v1/agents.py:194` | `validate_agent_version` — `POST /agents/versions/{id}/validate` | POST | `agent_version.validate` | `PRIVILEGED_ROLES` |
| `app/api/v1/agents.py:224` | `publish_agent_version` — `POST /agents/versions/{id}/publish` | POST | `agent_version.publish` | `PRIVILEGED_ROLES` |
| `app/api/v1/audit.py:31` | `list_audit_events` — `GET /audit/events` | GET | `audit_log.read` | `AUDIT_READ_ROLES` |
| `app/api/v1/eval.py:62` | `create_eval_run` — `POST /eval/runs` | POST | `eval_run.create` | `PRIVILEGED_ROLES` |
| `app/api/v1/knowledge.py` `create_source` | `create_source` — `POST /knowledge/sources` | POST | `knowledge_source.create` | `PRIVILEGED_ROLES` |
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

### 1-c. 읽기 측 게이트 전수 — 두 종류로 분류된 상태

초판 기준으로 **오직 문자열 `"admin"`만** 검사하는 읽기 게이트가 11곳 있었고, 왜
`PRIVILEGED_ROLES`(3역할)와 다른지 설명하는 주석이 하나도 없었다.
`WO-2026-08-13-ROLE-READ-COHERENCE`가 이 11곳을 하나씩 두 종류로 분류했다:

- **D = discovery-for-a-granted-mutation** — 그 역할이 **이미 보유한 뮤테이션**을 수행하려면
  반드시 거쳐야 하는 조회 단계. 대상을 찾을 수 없는 권한은 권한이 아니므로, 해당 뮤테이션과
  같은 집합(`PRIVILEGED_ROLES`)으로 맞췄다.
- **B = general ACL bypass** — "권한과 무관하게 전부 본다". 어떤 뮤테이션 권한도 이것을
  함의하지 않으므로 **리터럴 `"admin"` 그대로 유지**했다. 넓히지 않았다.

| 파일 | 용도 | 분류 | 현재 게이트 |
|---|---|:---:|---|
| `agents.py` `list_agents` | 미공개 에이전트 목록 | **D** | `PRIVILEGED_ROLES` (`_is_builder`) |
| `agents.py` `get_agent` | 미공개 에이전트 단건(없으면 404로 존재 은닉) | **D** | `PRIVILEGED_ROLES` (`_is_builder`) |
| `agents.py` `list_agent_versions` | 미공개 에이전트의 draft/validated 버전 | **D** | `PRIVILEGED_ROLES` (`_is_builder`) |
| `knowledge.py` `list_documents` — `include_archived` | 보관(archived) 문서 **행 발견** | **D** | `PRIVILEGED_ROLES` + **ACL 그대로 적용** |
| `knowledge.py` `list_documents` — ACL 필터 생략 | 권한 무관 전체 문서 메타데이터 | **B** | 리터럴 `"admin"` (변경 없음) |
| `knowledge.py` `list_sources` | 지식소스 등급 필터 생략 | **B** | 리터럴 `"admin"` (변경 없음) |
| `knowledge.py` `create_index_job` 읽기-ACL | 문서 읽기 권한 없으면 403 | **B** | 리터럴 `"admin"` (변경 없음) |
| `knowledge.py` `process_index_job` 읽기-ACL | 위와 동일 | **B** | 리터럴 `"admin"` (변경 없음) |
| `knowledge.py` `get_index_job` | 위와 동일 | **B** | 리터럴 `"admin"` (변경 없음) |
| `knowledge.py` `list_document_chunks` | 위와 동일 | **B** | 리터럴 `"admin"` (변경 없음) |
| `runs.py` `_can_read_run` | 타인 run의 답변/트레이스 | **B** | 리터럴 `"admin"` (변경 없음) |
| `runs.py` `list_runs` | 타인 run 목록 | **B** | 리터럴 `"admin"` (변경 없음) |

(초판의 11곳이 12줄이 된 이유: `list_documents`의 `is_admin` **하나**가 서로 다른 두 가지를
동시에 게이트하고 있었다 — 보관 문서 발견(D)과 ACL 필터 생략(B). 이 둘을 분리한 것이 이번
작업의 핵심이다. 리터럴 `"admin"` 체크는 이제 코드상 8곳이다: `knowledge.py` 6, `runs.py` 2.)

**왜 D는 넓히고 B는 안 넓혔나**

- D-문서(`include_archived`): `restore`(`POST /documents/{id}/restore`)는 이미
  `PRIVILEGED_ROLES` 전체에 열려 있는데, 보관 문서는 `principal_can_access_document`의
  **상태 게이트**에 걸려 목록에 뜨지 않았다. 즉 `knowledge-manager`는 복원할 수 있지만 복원할
  대상의 id를 찾을 방법이 없었다 — 그 플래그의 코드 주석("admins can discover an archived
  document's id to restore it")이 설명하는 바로 그 워크플로가 복원 권한자 3명 중 2명에게
  막혀 있었다.
- D-에이전트: `knowledge-manager`는 버전을 `validate`/`publish`할 수 있는데 미공개 에이전트의
  버전 목록에서는 404를 받았다. 게다가 이 역할은 **이미** `PATCH /agents/{id}`(빈 바디)와
  `POST /agents/versions/{id}/validate`로 같은 데이터를 읽을 수 있었다(두 경로 모두
  공개상태를 검사하지 않음). 즉 종전 게이트가 실제로 막고 있던 것은 데이터 자체가 아니라
  **열거(enumeration)** 뿐이었고, 열거야말로 "발행할 수 있다"를 실행 가능한 워크플로로
  만드는 단계다.
- B: `knowledge-manager`에게 전체 문서 메타데이터·타인 run·등급 초과 지식소스를 여는 것은
  어떤 뮤테이션 권한으로도 정당화되지 않는 **권한 상승**이다. Work Order가 명시적으로 금지한
  항목이기도 하다.

**남은(의도적) 비대칭 — 파일럿에서 알고 있어야 할 것**: `archive`/`restore`/`acl_update`는
**ACL을 전혀 보지 않는다**(`PRIVILEGED_ROLES`만 검사). 반면 위 D-문서 발견은 ACL을 적용한다.
따라서 `knowledge-manager`는 자기 ACL 밖 문서라도 **id를 알면** 보관/복원할 수 있지만, 그런
문서를 **목록에서 찾아낼 수는 없다**. 이 간극을 완전히 없애려면 (a) 발견 범위를 ACL 밖으로
넓히거나 — 금지된 일반 바이패스 확대 — (b) 보관/복원에 ACL 검사를 추가해 **권한을 축소**해야
하는데, 후자는 역할의 권한을 줄이는 **제품 결정**이므로 이 Work Order에서 하지 않았다.

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
# apps/api/app/domain/acl.py
def _acl_permits(principal: Principal, document: Document) -> bool:
    """ACL 판정 본체 — 라이프사이클 상태는 보지 않는다."""
    if document.confidentiality_level in EXCLUDED_INDEX_CONFIDENTIALITY_LEVELS:  # ② 등급 전면 배제
        return False
    if principal_clearance_rank(principal.clearance_level) < confidentiality_rank(
        document.confidentiality_level
    ):                                                                # ③ 등급 비교
        return False
    if not document.access_groups:                                   # ④ 빈 그룹 = 아무도 못 봄
        return False
    return bool(principal_acl_subjects(principal).intersection(document.access_groups))  # ⑤ 교집합


def principal_can_access_document(principal: Principal, document: Document) -> bool:
    if document.status not in SEARCHABLE_DOCUMENT_STATUSES:          # ① 상태 게이트
        return False
    return _acl_permits(principal, document)


def principal_can_discover_archived_document(principal, document) -> bool:
    if document.status != "archived":                                # ①' 상태 게이트(보관 전용)
        return False
    return _acl_permits(principal, document)
```

**두 술어의 관계(`WO-2026-08-13-ROLE-READ-COHERENCE`에서 추가)**: `_acl_permits`가 ACL 판정
**본체**이고, 두 공개 술어는 **①번 라이프사이클 상태 게이트만** 다르다. ②③④⑤는 한 벌의 코드를
공유하므로 둘이 갈라질 수 없다. `principal_can_discover_archived_document`는 §1-c의 D-문서
분류에 해당하는 **메타데이터 행 발견** 전용이며, 청크 조회·검색·retrieval은 전부 여전히
`principal_can_access_document`를 쓴다 — 즉 보관 문서의 **본문은 아무도 못 읽는다**. 호출부는
이 술어와 별개로 복원 권한(`PRIVILEGED_ROLES`) 자체도 요구한다(ACL만으로는 부족).

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
**D** = 부여된 뮤테이션을 위한 발견(§1-c, ACL은 그대로 적용), **B** = 일반 ACL 바이패스
(리터럴 `"admin"` 전용), 그 외 모두 = 없음(계정 소유 데이터/ACL 통과분만).

| 기능 | admin | platform-admin | knowledge-manager | security-auditor | 그 외(예: developer) |
|---|:---:|:---:|:---:|:---:|:---:|
| 에이전트 **생성**(`POST /agents`) — **게이트 없음** | O | O | O | O | **O** (⚠ §10-b) |
| 에이전트 수정/버전생성/검증/발행 | O (P) | O (P) | O (P) | X | X |
| 지식소스 생성(`POST /knowledge/sources`) | O (P) | O (P) | O (P) | X | X |
| 문서 등록/업로드/ACL수정/보관/복원/재색인 | O (P) | O (P) | O (P) | X | X |
| 최초 색인(문서를 읽을 수 있는 principal만) | O | O | O | O(읽기ACL 통과 시) | O(읽기ACL 통과 시) |
| Eval 결과 기록 | O (P) | O (P) | O (P) | X | X |
| 감사 로그 조회(`GET /audit/events`) | O (A) | O (A) | X | O (A) | X |
| 미공개 에이전트/버전 조회·열거 (**D**) | O | O | O | X | X |
| 보관 문서 발견(`include_archived`) (**D**) | O (B로 전부) | O(**자기 ACL 내만**) | O(**자기 ACL 내만**) | X | X |
| 전체 문서 메타데이터(ACL 무시) (**B**) | O | X | X | X | X |
| 타인 run 조회 (**B**) | O | X | X | X | X |
| 등급 초과 지식소스 조회 (**B**) | O | X | X | X | X |
| 본인 소유 run 조회 | O | O | O | O | O |
| 등급·그룹 조건을 만족하는 문서 검색/열람 | O | O | O | O | O(조건 만족 시) |

첫 행의 경고: `POST /agents`(`create_agent`)에는 **인가 검사가 아예 없다**. 초판의 이 표는
"에이전트 생성/수정/버전관리/검증/발행"을 한 행으로 묶어 전부 `PRIVILEGED_ROLES`라고 적었지만
그것은 **코드와 다른 서술**이었다 — `WO-2026-08-13-MUTATION-GATE-SWEEP`의 전수조사가 이를
발견해 행을 쪼개고 코드 쪽 사실로 정정했다(문서에 맞춰 코드를 바꾸지 않았다. 이유는 §10-b).

읽는 법: `knowledge-manager`/`platform-admin`은 이제 **자기가 바꿀 수 있는 것을 찾을 수는
있다**(D 행) — 미공개 에이전트를 열거하고, 자기 ACL 안의 보관 문서를 찾아 복원할 수 있다.
그러나 **권한과 무관하게 전부 보는 것**(B 행)은 여전히 `admin` 전용이다. `security-auditor`는
감사 로그만 볼 수 있고 D도 B도 없다(뮤테이션 권한이 없으므로 발견시켜 줄 대상이 없다).
이 넷 중 UI로 실제로 눌러볼 수 있는 것은 `admin`과 "그 외"뿐이다(§5) — 즉 **이번에 열린 D
경로는 UI로는 시연할 수 없고 헤더를 직접 보내야 확인된다**.

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

---

## 10. 상태변경 엔드포인트 인가 인벤토리 (`WO-2026-08-13-MUTATION-GATE-SWEEP`, 2026-08-13)

**왜 이 절이 있나.** 뮤테이션 엔드포인트의 인가 누락이 서로 무관한 조사에서 **네 번** 따로
발견됐다 — PR #66/#83(인덱스 잡), PR #92(재색인 신뢰경계), `WO-2026-08-12-UPLOAD-ROLE-GATE`
(register/upload), 그리고 다른 작업 중 **우연히** 발견된 `create_source`. 매번 하나씩 고쳤다.
**패턴이 결함이었다**: 게이트 없는 뮤테이션의 집합이 "불완전"한 게 아니라 **알 수 없는**
상태였고, 코드만 봐서는 *실수로 안 막은 것*과 *일부러 열어둔 것*이 완전히 똑같이 보였다.

**도출 방식(손목록 금지).** 아래 표는 **앱의 실제 라우트 테이블에서 기계적으로 추출**한다
(`fastapi.routing.iter_route_contexts` — FastAPI 0.139부터 `include_router`가
`app.routes`에 평탄화되지 않기 때문에 필요) + **OpenAPI 스키마로 교차검증**(워커가 조용히
누락하는 경우를 잡는 두 번째 독립 도출). 손으로 유지하는 목록은 만들지 않는다 — 지금까지
구멍이 살아남은 방식이 바로 손목록이었다.

**강제 장치.** `apps/api/tests/test_route_authorization_inventory.py`. 결정이 기록되지 않은
`POST`/`PUT`/`PATCH`/`DELETE` 라우트가 하나라도 있으면 **스위트가 빨개진다**. 추가로
(a) `role-gated`로 기록된 라우트의 함수 본문에 `enforce_roles` 호출이 실제로 있는지,
(b) 그 밖의 분류는 **코드 현장에 `AUTHZ-DECISION:` 주석으로 이유가 적혀 있는지**,
(c) 이 §10 표에 그 경로가 실제로 적혀 있는지까지 검사한다(문서 드리프트 방지).

**분류 4종**

| 분류 | 뜻 |
|---|---|
| `role-gated` | `enforce_roles`로 역할 집합을 강제 |
| `acl-gated` | 인가가 **대상 리소스의 ACL**에서 나온다 |
| `deliberately-open` | 의도적으로 열어둠 — **이유를 현장에 적어야 한다** |
| `unclosed-gap` | 알려진 미해결 구멍. 닫으면 **실효 권한이 줄어들어** 제품 결정이 필요하므로 여기서 닫지 않았고, **소관 Work Order/결정 기록을 명시**해야 한다 |

### 10-a. 전수 인벤토리 (16개 라우트)

| 메서드 · 경로 | 함수 | 분류 | 인가 근거 | 미해결 갭 |
|---|---|---|---|---|
| `POST /api/v1/agents` | `create_agent` | **unclosed-gap** | **없음** — 어떤 principal이든 생성 가능 | §10-c ①(보고만) |
| `PATCH /api/v1/agents/{agent_id}` | `update_agent` | role-gated | `PRIVILEGED_ROLES` / `agent.update` | — |
| `POST /api/v1/agents/versions` | `create_agent_version` | role-gated | `PRIVILEGED_ROLES` / `agent_version.create` | — |
| `POST /api/v1/agents/versions/{version_id}/validate` | `validate_agent_version` | role-gated | `PRIVILEGED_ROLES` / `agent_version.validate` | — |
| `POST /api/v1/agents/versions/{version_id}/publish` | `publish_agent_version` | role-gated | `PRIVILEGED_ROLES` / `agent_version.publish` | — |
| `POST /api/v1/knowledge/sources` | `create_source` | role-gated | `PRIVILEGED_ROLES` / `knowledge_source.create` | — (§10-b에서 **이번에 닫음**) |
| `POST /api/v1/knowledge/documents` | `register_document` | role-gated | `PRIVILEGED_ROLES` / `document.register` | — |
| `POST /api/v1/knowledge/documents/upload` | `upload_document_and_index` | role-gated | `PRIVILEGED_ROLES` / `document.upload` | — |
| `DELETE /api/v1/knowledge/documents/{document_id}` | `archive_document` | role-gated | `PRIVILEGED_ROLES` / `document.archive` | §10-c ③ 대상-ACL 미검사 |
| `POST /api/v1/knowledge/documents/{document_id}/restore` | `restore_document` | role-gated | `PRIVILEGED_ROLES` / `document.restore` | §10-c ③ 대상-ACL 미검사 |
| `PATCH /api/v1/knowledge/documents/{document_id}/acl` | `update_document_acl` | role-gated | `PRIVILEGED_ROLES` / `document.acl_update` | §10-c ③ 대상-ACL 미검사 |
| `POST /api/v1/knowledge/documents/{document_id}/index-jobs` | `create_index_job` | acl-gated | 대상 문서 읽기-ACL + (`has_been_indexed`면) `PRIVILEGED_ROLES` | §10-c ② 최초색인 |
| `POST /api/v1/knowledge/index-jobs/{job_id}/process` | `process_index_job` | acl-gated | 위와 동일(2단 게이트) | §10-c ② 최초색인 |
| `POST /api/v1/knowledge/retrieval/preview` | `preview_retrieval` | deliberately-open | 호출자 자신의 ACL(`build_acl_filter`)만 적용, 도메인 상태 생성 없음 | — |
| `POST /api/v1/runs` | `create_run` | deliberately-open | 발행된 버전만 실행 가능 + 호출자 ACL로 검색 + 생성 행은 호출자 소유 | — |
| `POST /api/v1/eval/runs` | `create_eval_run` | role-gated | `PRIVILEGED_ROLES` / `eval_run.create` | — |

### 10-b. 이번에 닫은 것 — `create_source` 하나

`POST /knowledge/sources`에는 `enforce_roles` 호출이 **아예 없었다**. 실증 재현(2026-08-13,
hermetic TestClient): `X-Agent-Forge-Roles: developer`로도, **인증 헤더를 하나도 안 보내도**
(기본 스텁 = `developer`) `201`로 지식소스가 생성되고 `default_confidentiality_level`을
`restricted`로 골라 붙일 수 있었다. 이제 `PRIVILEGED_ROLES`로 게이트되며(`403` +
`policy.denied` 감사), 검증(`422`)보다 **인가를 먼저** 수행한다.

**실효 권한이 줄어드는가**: 사실상 아니다. 문서 등록/업로드는 이미
`WO-2026-08-12-UPLOAD-ROLE-GATE`로 `PRIVILEGED_ROLES` 전용이므로, 비권한 principal이 소스를
만들어도 **그 안에 아무 문서도 넣을 수 없었다** — 남는 것은 카탈로그에 잘못된 등급 라벨이 붙은
빈 행뿐이었다. 프런트엔드 `createSource`는 데모 역할 기본값이 `admin`이고, eval 하네스와
스모크 스크립트도 admin 헤더를 쓰므로 영향 없음.

### 10-c. 보고만 하고 닫지 않은 것 — 세 건 모두 **제품 결정**이 필요하다

이 세 건은 닫는 즉시 **누군가의 실효 권한이 줄어든다**. Work Order가 그런 게이트를 보고 없이
추가하는 것을 금지하므로, 여기서는 기록·보고만 한다.

**① `POST /agents`(`create_agent`)에 인가 검사가 없다 — 이번 전수조사에서 새로 발견**

실증 재현(2026-08-13, hermetic TestClient): `roles=developer`인 principal이
`{"status": "published"}`로 `POST /agents`를 호출해 `201`을 받고, 그 다음 **아무 헤더도 없는**
기본 스텁 principal의 `GET /agents`에 그 에이전트가 그대로 보였다. `AgentCreate.status`는
호출자가 지정할 수 있고 검증되지 않는데, `list_agents`/`get_agent`는 비-빌더에게
`status == "published"`만 보여주므로 — **발행 게이트(`publish_agent_version`,
`PATCH /agents`는 둘 다 `PRIVILEGED_ROLES`)를 우회해 카탈로그에 행을 심을 수 있다.**
영향의 정직한 상한: 실행은 안 된다(`POST /runs`는 발행된 `AgentVersion`을 요구하고
`create_agent_version`은 게이트됨). 따라서 실질 위험은 "사칭 가능한 카탈로그 항목"(예: 사내
사용자가 신뢰할 만한 이름의 가짜 에이전트)이고, 실행 가능한 에이전트 탈취는 아니다.
**결정이 필요한 이유**: 게이트하면 셀프서비스 에이전트 생성이 사라진다 — "에이전트 빌더"
제품에서 그것은 보안 결정이 아니라 제품 결정이다. 최소 두 개의 분리된 질문이다:
(a) 비권한 principal이 draft 에이전트를 만들 수 있어야 하는가,
(b) 만들 수 있다 해도 `status`를 호출자가 지정할 수 있어야 하는가(=발행 게이트 우회).
(b)만 막는 것(생성 시 `status`를 서버가 `draft`로 고정)은 (a)를 유지하면서 우회를 없애는
가장 좁은 선택지로 보이지만, 그 역시 실효 동작 변경이므로 이 Work Order에서 하지 않았다.

**② 최초 색인 경로 — `WO-2026-08-13-FIRST-INDEX-GATE`(draft) 소관**

`POST /documents/{id}/index-jobs`와 `/index-jobs/{id}/process`는 문서가
`has_been_indexed == False`인 동안 **읽기 권한만 있는** principal이 넘긴 `source_text`를
그 문서의 confidentiality/ACL 라벨 그대로 임베딩한다. `WO-2026-08-12-UPLOAD-ROLE-GATE`의
AC-04가 이미 "최초 색인 경로는 열려 있다"고 기록했고, 별도 Work Order가 결정을 기다린다.
이 Work Order는 그 결정을 **하지 않는다**(명시적 금지 항목).

**③ `archive`/`restore`/`acl_update`가 대상 문서의 ACL을 보지 않는다**

세 엔드포인트 모두 역할만 검사한다. 따라서 `knowledge-manager`는 자기 ACL 밖 문서라도 **id를
알면** 보관/복원/재라벨할 수 있다(목록으로는 찾을 수 없다 — §1-c 참고). 가장 날카로운 것은
`acl_update`다: 자기가 읽을 수 없는 문서의 접근 그룹·등급을 바꿀 수 있다. 닫으면 세 역할의
권한이 **줄어들기** 때문에 제품 결정이며, `WO-2026-08-13-ROLE-READ-COHERENCE`도 같은 이유로
남겼다. 세 곳 모두 코드 현장에 이 사실을 주석으로 명시했다.

### 10-d. 이 장치가 증명하지 않는 것 (정직한 한계)

- **결정이 기록됐음**을 증명하지, **결정이 옳음**을 증명하지 않는다. 잘못 분류해도 통과한다.
  리뷰어가 다툴 대상은 분류이고, 이 장치가 불가능하게 만든 것은 **분류의 부재**다.
- `role-gated` 검사는 함수 본문에 `enforce_roles(` 호출이 **있는지**만 본다 — 인자(역할 집합)나
  **위치**(부작용 이전인지)는 보지 않는다. 그건 엔드포인트별 테스트의 몫이다
  (`test_source_role_gate.py`, `test_ingestion_role_gate.py`, `test_metadata_contracts.py`).
- **읽기(GET) 엔드포인트는 이 인벤토리 대상이 아니다.** 읽기 측 게이트는 §1-c에 있고, 이
  Work Order는 읽기 엔드포인트를 건드리지 않았다. 읽기 쪽에도 같은 강제 장치가 필요한지는
  별도 판단 사항이다.
- 신원 자체는 여전히 검증되지 않은 헤더다(§7-b, ADR-103 `OPEN`). 인가 결정이 전수 기록됐다는
  것이 "누가 그 역할을 주장했는지 믿을 수 있다"는 뜻은 아니다.
