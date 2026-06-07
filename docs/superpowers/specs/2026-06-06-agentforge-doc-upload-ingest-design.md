# AgentForge — 문서 업로드/인제스트 (TXT/MD) 설계

- 날짜: 2026-06-06
- 상태: 설계 승인 대기
- Epic: EP-02 Knowledge ingestion (얇은 슬라이스)
- 선행: register+index(source_text) 경로 + 진짜 벡터검색(Qdrant+bge-m3) + 에이전트 빌더 UI 모두 main에 있음.

## 1. 목적과 범위

운영자가 지식소스에 **TXT/MD 문서를 직접 추가(업로드/붙여넣기)** 하면 실제 bge-m3 임베딩으로 Qdrant에 색인되어, 그 소스를 연결한 에이전트가 해당 문서 근거로 답한다. **백엔드 무변경** — 기존 `POST /knowledge/sources`, `POST /knowledge/documents`, `POST /knowledge/documents/{id}/index-jobs`(source_text 동기 색인) 재사용.

### 포함
- `/knowledge` 페이지: 소스/문서 목록 + "문서 추가" 폼.
- 기존 소스 선택 또는 **새 소스 인라인 생성**.
- `.txt/.md` 파일 업로드(브라우저에서 텍스트로 읽음) 또는 붙여넣기.
- 권한 지정: 기밀등급(공개/내부/제한) + 접근그룹(기본 all-employees, 편집 가능).
- 색인 결과(청크 수/상태) 표시.

### 제외 (다음 슬라이스)
PDF/DOCX/XLSX 파싱(서버 파서 라이브러리 필요), MinIO 객체저장(원본 파일 보관), 대용량/비동기 인제스트, 재색인 UI. (파서는 mime_type별 교체 구조라 추후 파서만 추가하면 확장됨 — 다운스트림 청킹·임베딩·ACL 색인 무변경.)

## 2. 파일 구조
- 수정 `apps/web/app/knowledge/page.tsx` — 스캐폴드 → 소스/문서 목록 + 추가 폼(클라이언트).
- 수정 `apps/web/app/lib/api.ts` — `createSource`, `registerDocument`, `indexDocument` 추가.
- 신규 `apps/web/tests/knowledge-upload.spec.ts` — Playwright 렌더/유효성.
- 백엔드: 변경 없음.

## 3. lib/api.ts 헬퍼 (추가)
```
createSource({name, owner_department})        -> POST /knowledge/sources (OPERATOR 헤더)
registerDocument({knowledge_source_id, title, mime_type, confidentiality_level, access_groups, object_uri, checksum})
                                              -> POST /knowledge/documents (OPERATOR)
indexDocument({document_id, source_text})     -> POST /knowledge/documents/{id}/index-jobs
        {parser_profile:"default-txt-md", embedding_model:"bge-m3", source_text}  (동기 색인, IndexJobRead 반환)
sha256Hex(text)                               -> crypto.subtle 로 체크섬 계산(클라이언트)
```

## 4. "문서 추가" 폼 흐름
입력: ①소스(기존 선택 ▾ 또는 새 이름) ②제목 ③본문(파일 `.txt/.md` 선택 시 FileReader로 textarea에 채움, 또는 직접 붙여넣기) ④기밀등급(기본 internal) ⑤접근그룹(기본 `all-employees`).

"추가 & 색인" 클릭 시:
1. 새 소스면 `createSource({name, owner_department:"Operations"})` → source_id 확보.
2. `registerDocument`: `object_uri = "inline://" + (파일명 또는 제목)`, `checksum = "sha256-" + sha256Hex(본문)`, `mime_type = 파일명이 .md로 끝나면 "text/markdown" 아니면 "text/plain"`, 지정한 confidentiality·access_groups(쉼표 분해), `status:"registered"`.
3. `indexDocument({document_id, source_text:본문})` → 동기 색인(bge-m3→Qdrant). 반환 `chunk_count`·`status`.
4. 결과 표시: 성공 "색인됨 N청크", 실패 시 `error_code/error_message`.

mime는 `text/plain`/`text/markdown`만 — 기존 `parse_txt_md_document`가 지원(그 외엔 `UNSUPPORTED_MIME_TYPE`로 실패).

## 5. 통합 효과
색인 성공 시 그 소스가 빌더(`/agents/new`) ② 단계에서 **"색인됨 N" 배지로 선택 가능** → 게시 → 그 문서 근거 답변. 운영자가 자기 문서로 에이전트를 만드는 전체 한 바퀴 완성.

## 6. 에러 처리
- 필수: 소스(선택 또는 새 이름) + 제목 + 본문 비어있지 않음. 그 전까지 "추가 & 색인" 비활성.
- 접근그룹 비어있으면 기본 `all-employees` 적용(빈 그룹은 백엔드에서 `DOCUMENT_NOT_INDEXABLE`로 실패 → deny-by-default와 일치하므로 UI에서 기본값 보장).
- 색인 실패 시 job의 `error_code/error_message` 인라인 표시. 색인 중 버튼 비활성+"색인 중…".
- 소스 생성/등록 실패 시 인라인 에러, 만들어진 source_id/document_id는 상태 보존(재시도 시 재개, 중복 방지) — 빌더의 멱등 패턴과 동일.

## 7. 테스트
- **Playwright** `knowledge-upload.spec.ts`(렌더 전용, 기존 패턴): `/knowledge`에 "문서 추가" 폼·제목/본문 입력 보임, 비어있을 때 "추가 & 색인" `disabled`.
- **라이브 수동**: 작은 `.md`(예: "출장 규정\n출장비는 일 5만원...") 업로드 → "색인됨 N" → 빌더에서 그 소스 연결·게시 → "출장비 얼마?" 질문 → 새 문서 근거 답변(출처). Qdrant points 증가 확인.
- 백엔드 무변경 → `apps/api` 56 passed 무영향.

## 8. 영향 파일 요약
- 수정: `apps/web/app/knowledge/page.tsx`, `apps/web/app/lib/api.ts`
- 신규: `apps/web/tests/knowledge-upload.spec.ts`
- 백엔드: 없음
