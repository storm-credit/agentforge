# RAG Design

## 목적

Agent Forge MVP의 RAG는 사내 문서를 기반으로 권한 안전한 답변을 생성하는 기능이다. 핵심 원칙은 원본 보존, deterministic indexing, ACL-first retrieval, citation-required answer다.

## 문서 파이프라인

```text
수집
-> 원본 저장
-> 변경 감지/중복 제거
-> 파싱
-> 정규화
-> chunking
-> metadata/ACL 부여
-> embedding
-> lexical/vector indexing
-> snapshot 발행
```

## 수집

MVP 지원 소스는 사내 파일 서버, 그룹웨어 export, 관리자 수동 업로드다. 수집기는 원본을 수정하지 않고 raw storage에 저장한다.

```yaml
source_id: "security_policy_docs"
source_type: "file_share"
owner_department: "security"
allowed_extensions: [".pdf", ".docx", ".xlsx", ".txt", ".md"]
default_acl:
  department_scope: ["all"]
  role_scope: ["employee"]
  confidentiality_level: "internal"
```

## Parsing

| 형식 | 추출 구조 | citation locator |
|---|---|---|
| PDF | page, text block, table | page/block |
| DOCX | heading, paragraph, table, list | heading/paragraph |
| XLSX | sheet, table range, row/column | sheet/cell range |
| TXT | line range, section | line range |
| Markdown | heading, table, code block | heading/line range |

파싱 confidence가 낮거나 ACL을 확인할 수 없는 문서는 quarantine 처리한다.

## Chunking

| 항목 | 기준 |
|---|---|
| target | 650 tokens |
| min/max | 250 / 900 tokens |
| overlap | 80-120 tokens |
| split 우선순위 | heading, paragraph, sentence, token |
| table | 한 표를 가능하면 하나의 chunk로 유지 |

chunk ID는 재현 가능한 값이어야 한다.

```text
{document_id}:{document_version}:{structure_locator}:{chunk_index}:{chunk_hash_prefix}
```

## 필수 Chunk Metadata

```yaml
chunk_id: "sec-policy-2026:2026.05.01:p12:c03:8f2a91"
document_id: "sec-policy-2026"
document_version: "2026.05.01"
source_id: "security_policy_docs"
title: "외부 반출 보안 절차"
section: "3.2 로그 및 진단자료"
page_start: 12
page_end: 12
content_hash: "sha256-..."
chunk_hash: "sha256-..."
indexed_at: "2026-05-09T09:10:00+09:00"
embedding_model: "internal-embedding-ko-v1"
acl:
  department_scope: ["all"]
  role_scope: ["employee"]
  project_scope: ["corp-policy"]
  confidentiality_level: "internal"
```

## Embedding/Indexing

- embedding 모델은 사내망에서 실행 가능한 registry 등록 모델만 사용한다.
- embedding 입력에는 title, section, content를 포함한다.
- ACL/기밀 metadata는 embedding text에 넣지 않는다.
- embedding 모델 변경 시 새 index snapshot을 만든다.
- vector index와 lexical index를 함께 사용한다.
- Sprint 1 uses a deterministic fake vector adapter to lock the interface before real backends are promoted.
- Sprint 2 Qdrant wiring is available behind `AGENT_FORGE_VECTOR_STORE_BACKEND=qdrant`; it stores chunk payload metadata in Qdrant and pushes status, knowledge source, clearance, and access-group filters into the vector query before ranking.
- Vector search requires an ACL filter and returns only allowed chunk IDs, citation locators, hashes, ranks, and scores.

## ACL-aware Retrieval

검색 순서:

```text
IAM 권한 컨텍스트 생성
-> Agent Card knowledge source 검증
-> query embedding
-> ACL payload filter 생성
-> vector + lexical search
-> hybrid merge
-> rerank
-> citation 후보 선택
-> LLM context 구성
```

ACL filter 의미:

```text
deny_user_ids에 사용자가 없어야 함
AND department_scope가 all 또는 사용자 부서와 일치
AND role_scope가 사용자 role과 교집합
AND project_scope가 사용자 project_scope와 교집합
AND confidentiality_rank <= user.clearance_rank
AND 문서 유효 기간 안에 있음
```

MVP confidentiality rank is `public=0`, `internal=1`, `restricted=2`, and `confidential=3`. Confidential documents are excluded from the default MVP search index.

ACL filter는 vector search 이전에 적용한다. 권한 밖 chunk는 rerank, LLM context, 일반 로그에 들어가면 안 된다.

## Rerank

MVP는 hybrid search 후보 40-60개를 대상으로 rerank하고 최종 6개 이하의 context chunk를 사용한다.

기본 기준:

- rerank top-k: 8
- min rerank score: 0.62
- max context chunks: 6
- 동일 문서 중복 chunk는 필요 시 2-3개로 제한
- 최신 effective date 문서를 우선

## Citation

사용자 노출 형식:

```text
[외부 반출 보안 절차, 3.2 로그 및 진단자료, p.12, v2026.05.01]
```

노출하지 않는 값:

- 내부 파일 서버 경로
- object storage URI
- 작성자 개인 ID
- 권한 필터식
- 사용자가 권한 없는 문서의 존재 여부

근거형 답변에는 citation이 필수다. citation이 없으면 Critic이 재작성 또는 안전 실패를 요청한다.

## MVP Quality Gates

- parse success rate 소스별 95% 이상
- ACL 필수 필드 coverage 100%
- `document_id`, `chunk_id`, `title`, `citation_locator` 누락 chunk 0건
- golden query top-k recall 기준 통과
- 권한 회수 후 5분 이내 retrieval 차단
- prompt injection 문서가 상위 검색되더라도 시스템 지시를 변경하지 않음
- citation locator가 실제 원문 위치와 일치
- audit log에 `run_id`, `build_id`, `index_snapshot_id`, `retrieved_chunk_ids`, `acl_filter_hash` 기록
