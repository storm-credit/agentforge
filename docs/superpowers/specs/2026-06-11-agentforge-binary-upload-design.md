# AgentForge — PDF/DOCX 업로드 인제스트 설계

- 날짜: 2026-06-11
- 상태: 승인됨 (설계+구현단계 통합)
- 동기: 현재 업로드는 TXT/MD(브라우저 텍스트→source_text)만. 진짜 사내문서(PDF/DOCX)를 서버에서 텍스트 추출해 기존 색인 파이프라인으로.

## 1. 결정
- (a) PDF + DOCX (XLSX 후순위). (b) MinIO 생략(YAGNI) — 텍스트만 추출, 원본 미보관. (c) 신규 멀티파트 업로드 엔드포인트. (d) parsers.extract_text + 청킹 재사용.
- 보안: 크기/페이지 상한, 추출 실패/빈 → job failed.

## 2. 구현 단계 (TDD)
1. **deps**: `pyproject.toml`에 `pypdf`, `python-docx`, `python-multipart`. `.venv` 설치.
2. **`app/domain/parsers.py`**: `extract_text(mime_type: str, file_bytes: bytes) -> str`:
   - text/plain·text/markdown·text/x-markdown → `data.decode("utf-8", errors="replace")`.
   - application/pdf → pypdf `PdfReader(BytesIO(data))`, 최대 `MAX_PDF_PAGES=50` 페이지 텍스트 결합.
   - application/vnd.openxmlformats-officedocument.wordprocessingml.document → python-docx `Document(BytesIO)` 문단 결합.
   - 그 외 → `ValueError("Unsupported upload MIME type: ...")`.
   - 단위테스트: DOCX 라운드트립(python-docx로 생성→추출, 한국어), TXT decode, 미지원 mime→ValueError, PDF는 커밋 픽스처(영문)로 추출 검증.
3. **`app/domain/indexing.py`** `run_index_job`: 비텍스트 MIME이면 `source_bytes`에서 텍스트를 추출한 뒤 기존 `text/plain` 청커로 넘긴다. 기존 TXT/MD `source_text` 경로는 불변.
4. **`app/api/v1/knowledge.py`**: `POST /documents/upload`(`UploadFile`): bytes 읽기(크기 상한 `MAX_EXTRACT_BYTES=10MB`) → Document + IndexJob 생성 → `run_index_job(source_bytes=raw)` → 추출 실패/빈 텍스트면 job `failed`, 성공하면 `{document, index_job}` 반환.
   - 계약 테스트: 멀티파트로 작은 PDF/DOCX 업로드 → 색인 succeeded, 청크>0.
5. **프론트** `apps/web/app/knowledge/page.tsx`: 파일 입력 `accept=".txt,.md,.pdf,.docx"`. 파일 선택 시 바이너리(pdf/docx)면 `uploadDocument`(멀티파트); txt/md·붙여넣기는 기존 source_text 경로. `lib/api.ts`에 `uploadDocument`.

## 3. 검증
- pytest(.env 옆으로) 기준 70 + 신규 그린, ruff 클린. security-review 스킬.
- 라이브: 작은 .pdf/.docx 업로드→색인 succeeded→빌더 연결·게시→근거 답변(grounding 0.1·게이팅 0.53 통과).

## 4. 영향 파일
`pyproject.toml`, `app/domain/parsers.py`(extract_text), `app/domain/indexing.py`(binary extraction wiring), `app/api/v1/knowledge.py`(multipart endpoint), `apps/web/app/lib/api.ts`·`apps/web/app/knowledge/page.tsx`, 테스트(parsers 단위 + 업로드 계약 + knowledge 렌더).
