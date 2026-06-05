# AgentForge — 에이전트 빌더 UI (가이드형 한 화면) 설계

- 날짜: 2026-06-06
- 상태: 설계 승인 대기
- Epic: EP-05 Agent Studio (얇은 수직 슬라이스)
- 선행: 에이전트/지식소스/런타임 API + 진짜 벡터검색(Qdrant+bge-m3)이 main에 있음.

## 1. 목적과 범위

운영자가 **한 화면에서** "에이전트 생성 → 기존 지식소스 연결 → 게시 → 채팅 테스트" 한 바퀴를 끝낸다. 백엔드는 무변경 — 기존 API(`/agents`, `/agents/versions`, `/agents/versions/{id}/publish`, `/knowledge/sources`, `/knowledge/documents`, `/runs`)에 **프론트만 배선**.

### 레이아웃 결정
**가이드형 한 화면(B)**. 입력이 적어 마법사(다단계 페이지)는 과하다. 한 화면에 다 보이되 번호(①②③)로 순서를 안내하고, 테스트 패널은 게시 후 활성화. (설정이 7~8개 이상으로 커지면 그때 단계/탭으로 진화 — 이번엔 아님.)

### 포함
- `/agents` 목록 + "새 에이전트 만들기" 버튼
- `/agents/new` 가이드형 빌더(클라이언트 컴포넌트)
- 기존 **지식소스 선택만** 연결(문서 업로드/색인 제외)
- 게시 후 인라인 채팅 테스트(기존 `ask()` 재사용)
- 보강 5종(아래 §5)

### 제외 (다음 슬라이스)
재게시/버전관리, 에이전트 수정/삭제, 새 지식소스 생성·문서 업로드, 실제 운영자 인증(SSO — 백로그의 알려진 의존성. 이번엔 고정 operator 헤더 스텁).

## 2. 라우트·파일 구조
- 수정 `apps/web/app/agents/page.tsx` — 스캐폴드 카드 → **에이전트 목록(상태 배지) + "새 에이전트 만들기" 링크**.
- 신규 `apps/web/app/agents/new/page.tsx` — 가이드형 빌더(클라이언트).
- 수정 `apps/web/app/lib/api.ts` — 빌더 헬퍼 + operator 헤더 추가.
- 신규 `apps/web/tests/agent-builder.spec.ts` — Playwright.

## 3. lib/api.ts 헬퍼 (추가)
```
OPERATOR 헤더 = { X-Agent-Forge-User: "operator", X-Agent-Forge-Department: "Operations",
                  X-Agent-Forge-Roles: "admin", X-Agent-Forge-Groups: "all-employees",
                  X-Agent-Forge-Clearance: "internal" }
listSources()            -> GET /knowledge/sources
listDocuments()          -> GET /knowledge/documents   (소스별 색인 문서 수 집계용)
createAgent({name,purpose,owner_department})            -> POST /agents (status "draft", OPERATOR 헤더)
createVersion({agent_id, knowledge_source_ids})         -> POST /agents/versions
        {version:1, status:"draft", config:{citation_required:true, knowledge_source_ids}}
publishVersion(version_id)                              -> POST /agents/versions/{id}/publish {reason:"published via Agent Studio"}
ask(...) (기존 재사용, agentId=신규 에이전트)
```
소스별 "색인 문서 수" = `listDocuments()`에서 `knowledge_source_id`로 묶어 `status==="indexed"` 개수.

## 4. 화면·데이터 흐름 (`/agents/new`)
**왼쪽(설정), 번호 안내:**
- ① 기본정보: 이름·목적·담당부서 입력.
- ② 지식소스 연결: `listSources()` + 색인문서수 배지("색인됨 N"). 체크박스 다중 선택. 비어있으면 빈 상태 안내(§5-4).
- ③ 게시: 버튼. **이름 비어있지 않음 AND 색인문서 보유 소스 1개 이상 선택** 일 때만 활성(§5-2).

**게시 클릭 시 (멱등, §5-1):** 컴포넌트 상태에 `agentId/versionId/published` 보관.
1. `agentId` 없으면 `createAgent()` → 저장
2. `versionId` 없으면 `createVersion({agent_id, knowledge_source_ids})` → 저장
3. `publishVersion(versionId)` → `published=true`
실패 시 만들어진 id는 보존하여 재클릭이 **실패 지점부터 재개**(중복 생성 금지).

**오른쪽(테스트):** `published` 전엔 흐리게 `🔒 게시하면 활성화`. 게시 후: 사용자(Finance/HR, 기본 Finance=all-employees)·언어(자동/한/영) + 질문 → `ask({agentId, …})` → 답변·출처 렌더(기존 채팅과 동일 표시).

## 5. 보강 (확정 반영)
1. **멱등 게시** — 위 §4. 중복 에이전트 방지, 실패 지점 재개.
2. **"내용 있는 소스" 배지** — 체크리스트에 소스별 색인문서수("색인됨 N") 표시. **색인문서 0개 소스는 체크박스 비활성 + "색인 0" 배지** → 답 못 하는 에이전트 게시를 원천 차단. 게시 활성 조건은 "색인문서 보유 소스 1개 이상 선택"(§4-③와 일치).
3. **로딩/콜드스타트 상태** — "게시 중…", "답변 생성 중(첫 질문은 모델 로딩으로 느릴 수 있어요)" 스피너/문구. 버튼 중복클릭 방지(disabled while pending).
4. **빈 상태** — 지식소스 0개면 "지식소스가 없습니다 — 시드 실행(`python -m app.seed_demo`) 또는 Knowledge에서 추가" 안내, 게시 비활성.
5. **게시 후 마무리** — "✓ 게시됨, 이제 테스트하세요" 표시 + 테스트 사용자 기본값을 문서 권한 있는 쪽(Finance/all-employees)으로 두어 "방금 게시했는데 거부?" 혼란 방지.

## 6. 에러 처리
- 게시 버튼: 이름 + 소스≥1 + (선택 소스 중 색인문서 보유) 전까지 비활성.
- 각 API 실패 → 인라인 에러 메시지, `published` 미설정, 테스트 패널 잠금 유지. (만들어진 id는 보존해 재시도 가능.)
- 테스트가 거부(권한/무내용)되면 답변 영역에 거부 메시지 그대로 노출(시스템 정상 동작).

## 7. 테스트
- **Playwright** `apps/web/tests/agent-builder.spec.ts` (기존 `chat.spec.ts` 패턴, 전체 스택+시드 기동 필요):
  - (a) 해피패스: `/agents/new` → 이름 입력 → 색인된 시드 소스 선택 → 게시 → 테스트 패널 활성 → 질문 → `[data-testid="answer"]` 노출.
  - (b) 유효성: 이름/소스 없을 때 게시 버튼 `disabled`.
  - (c) 빈 상태 문구: (소스 없는 상태가 가능한 경우) 안내 노출 — 환경상 어려우면 수동 확인으로 표기.
- **수동 라이브**: 브라우저에서 새 에이전트 생성→게시→"연차?" 질문→출처 답변(`vector_adapter="qdrant"`).
- 백엔드 무변경 → 기존 `apps/api` 56 passed 무영향.

## 8. 영향 파일 요약
- 신규: `apps/web/app/agents/new/page.tsx`, `apps/web/tests/agent-builder.spec.ts`
- 수정: `apps/web/app/agents/page.tsx`, `apps/web/app/lib/api.ts`
- 백엔드: 변경 없음
