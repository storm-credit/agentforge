# AgentForge — 진짜 벡터검색 (Qdrant + bge-m3) 설계

- 날짜: 2026-06-05
- 상태: 설계 승인 대기
- 스프린트: Sprint 2 "최소한의 진짜 RAG" 잔여분
- 선행: `2026-06-05-agentforge-mvp-chat-answer-design.md` (LLM 게이트웨이·인용 답변·언어)

## 1. 목적과 범위

`feat/mvp-chat-answer`까지로 답변 생성(LLM 게이트웨이)과 Test Chat UI는 동작하지만, **검색이 `FakeVectorStore`(키워드 겹침)** 라 실제 사내문서에서 Release Gate의 "유용 답변률 ≥80%"를 만족할 수 없다. 본 슬라이스는 기존 `VectorStore` Protocol에 **진짜 Qdrant 어댑터 1개**를 끼워 의미 기반 벡터검색으로 교체한다. ACL은 벡터쿼리 조건에 포함한다(implementation-plan 4.5 준수).

### 포함 (이번 슬라이스)
- 임베딩 게이트웨이(OpenAI 호환 `/v1/embeddings`, env 주입, bge-m3)
- `QdrantVectorStore`: `upsert_chunks` / `search` / `delete_document`
- env 기반 벡터스토어 팩토리(`get_vector_store()`), 기본값은 `FakeVectorStore`
- ACL을 Qdrant payload 필터로 적용 + 사후 ACL 불변식 검증
- 색인 파이프라인이 실제 임베딩을 upsert하도록 연결
- 데모 시드 재색인 + 라이브 검증

### 제외 (다음 슬라이스)
hybrid(lexical+vector) merge, reranker, query rewrite/planner, 유효기간 필터, `deny_user_ids`/`project_scope`(현재 모델에 없음), 다포맷 파싱(PDF/DOCX/XLSX), Run Trace Viewer UI, Agent Studio UI, feedback API.

## 2. 아키텍처 / 컴포넌트

기존 `get_gateway()`(LLM) 패턴을 그대로 따른다 — env 주입 + 팩토리 + Protocol.

### 2.1 EmbeddingGateway (신규 `app/services/embedding_gateway.py`)
- OpenAI 호환 `POST {base_url}/embeddings` 호출.
- env: `AGENT_FORGE_EMBEDDING_BASE_URL`, `AGENT_FORGE_EMBEDDING_MODEL`(기본 `bge-m3`), `AGENT_FORGE_EMBEDDING_DIM`(기본 1024), `AGENT_FORGE_EMBEDDING_TIMEOUT_SECONDS`(기본 30).
- `embed(texts: list[str]) -> list[list[float]]`. 미설정/오류 시 예외(`EmbeddingUnavailable`).
- `health()` — `/models` 또는 임베딩 1회 시도. LLM 게이트웨이와 동일한 구조.

### 2.2 QdrantVectorStore (신규 `app/infra/qdrant_store.py`)
`VectorStore` Protocol 구현. 컬렉션 alias `chunks_active`(=`VectorQuery.collection_alias` 기본값).
- 컬렉션 없으면 첫 upsert 시 임베딩 차원으로 생성(distance=Cosine).
- payload 인덱스: `access_groups`(keyword), `confidentiality_rank`(integer), `knowledge_source_id`(keyword), `document_id`(keyword), `status`(keyword).
- 의존성: `qdrant-client` (`apps/api/pyproject.toml` 추가). 클라이언트 base는 env `AGENT_FORGE_QDRANT_URL`(기본 `http://localhost:6333`).

### 2.3 팩토리 `get_vector_store()` (`app/domain/vector.py`)
- env `AGENT_FORGE_VECTOR_BACKEND` ∈ {`fake`(기본), `qdrant`}.
- `qdrant`이고 Qdrant/임베딩 설정이 있으면 `QdrantVectorStore`, 아니면 `FakeVectorStore`.
- `QdrantVectorStore`(app/infra)는 **함수 내부에서 지연 import** — domain→infra 레이어 순환 방지.
- `get_gateway()` 미러. `lru_cache` 미사용(요청별 가벼운 생성, 테스트 격리 용이).

### 2.4 Settings / 의존성
`app/core/config.py`에 위 env 필드 추가. `pyproject.toml`에 `qdrant-client` 추가.

## 3. 데이터 흐름

### 3.1 색인 (write path) — `app/domain/indexing.py`
파싱 → 청크 → `get_vector_store().upsert_chunks(...)`.

**인터페이스 확장 필요**: 현재 `VectorUpsertInput`은 `chunk_id/document_id/content_hash/embedding_model`뿐이라 임베딩·ACL 정보가 없다. 다음 필드를 추가한다(Fake는 무시 → 기존 동작 유지, Qdrant만 사용):
- `content: str`, `title: str`, `section_path: tuple[str, ...]`, `citation_locator: str`
- `access_groups: tuple[str, ...]`, `confidentiality_rank: int`, `knowledge_source_id: str`

임베딩 입력 텍스트 = `title + " \n" + section + " \n" + content` (ACL/기밀 metadata는 **임베딩 텍스트에 미포함** — rag-design 준수). `vector_ref` = Qdrant point id(=chunk_id). 색인 중 임베딩/Qdrant 오류 → 기존 패턴대로 job `failed` + `error_code=EMBEDDING_UNAVAILABLE`/`VECTOR_UPSERT_FAILED`, 미임베딩 청크는 저장하지 않음.

### 3.2 검색 (read path) — `app/api/v1/runs.py` `_search_authorized_context`
`FakeVectorStore()` 직접 호출 → `get_vector_store()` 로 교체. Qdrant 경로: query 임베딩 → payload 필터 ANN(top_k) → `VectorHit` 반환(payload만으로 self-contained, `documents` 인자 미사용).

## 4. ACL → Qdrant payload 필터 (보안 핵심)

upsert payload: `access_groups[]`, `confidentiality_rank(int)`, `knowledge_source_id`, `document_id`, `chunk_id`, `title`, `citation_locator`, `status`.

검색 필터(Qdrant `Filter`):
- `must`: `status == "indexed"` **AND** `confidentiality_rank <= clearance_rank(principal)` **AND** (요청 시) `knowledge_source_id IN 요청목록`
- `access_groups` **match-any** vs `principal_acl_subjects(principal)` (교집합 1개 이상). 빈 `access_groups` → 매칭 불가 = **deny-by-default**.
- `confidential`(rank 3) 문서는 색인에서 제외되며 rank 필터로도 차단.

이는 `app/domain/acl.py`의 `principal_can_access_document` 의미를 그대로 옮긴 것이다.

**방어 심층(사후 불변식)**: 검색 결과 각 hit를 payload 기준으로 `principal_can_access_document` 동치 재검증. 위반 hit는 **drop + 경고 로그**(이론상 0건). ACL 누출이 최우선 위험이라 in-query 필터 + 사후 검증을 모두 둔다.

## 5. 에러 처리 / 폴백

- **검색 시** Qdrant/임베딩 장애 → `runs.py` 검색부 try/except에서 **`FakeVectorStore`로 폴백**(이미 로드된 documents 사용). 무성 강등 방지를 위해 retriever 스텝 `output_summary`에 `vector_adapter="fake_fallback"`, `degraded=true` 기록. (Fake도 ACL 강제 → 누출 위험 없음. "거부"는 장애를 권한문제로 오인시켜 탈락.)
- **색인 시** 장애 → job `failed` + `error_code` (3.1).
- **컬렉션 없음/차원 불일치** → 첫 upsert에 임베딩 차원으로 컬렉션 자동 생성.

## 6. 테스트 (plan 완료조건 포함)

- **Fake ↔ Qdrant 계약 동치**: 같은 코퍼스에서 ACL allow/deny 결과 동일(plan 4.5 완료조건). `qdrant-client` **로컬(`:memory:`) 모드**로 hermetic — 외부 서비스 의존 없음, skip 0 유지.
- **EmbeddingGateway 단위테스트**: httpx monkeypatch(기존 `test_llm_gateway_contracts` 방식) — 정상 임베딩, 미설정, 오류.
- **ACL→Qdrant 필터 변환 테스트**: 권한 있는/없는 사용자, deny-by-default, clearance 등급 경계.
- **사후 불변식 테스트**: 일부러 권한 밖 payload를 섞어도 결과에서 drop됨.
- 기존 `apps/api` pytest **40 + eval 7** 그린 유지(skip 0).
- **라이브 검증**: 시드 재색인(실 bge-m3 임베딩) → Finance 한국어 질의 출처 답변(생성 스텝 `mode=llm`, retriever `vector_adapter="qdrant"`), 권한 없는 사용자 거부, 폴백 강등 표시.

## 7. 운영 / 사내 이관

신규 env만 추가, Qdrant 컬렉션 `chunks_active`. 사내 이관 = 임베딩 `base_url/model`을 사내 registry(`internal-embedding-ko-v1`)로, `AGENT_FORGE_QDRANT_URL`만 교체(무코드). 임베딩 모델 변경 시 새 컬렉션 스냅샷 + 재색인.

## 8. 영향 파일 (요약)
- 신규: `app/services/embedding_gateway.py`, `app/infra/qdrant_store.py`, 테스트 3~4개
- 수정: `app/domain/vector.py`(`VectorUpsertInput` 확장 + `get_vector_store()`), `app/domain/indexing.py`(실 upsert), `app/api/v1/runs.py`(팩토리+폴백), `app/core/config.py`(env), `apps/api/pyproject.toml`(qdrant-client)
- 무변경 보장: `app/domain/acl.py` 의미, 기존 `FakeVectorStore` 동작
