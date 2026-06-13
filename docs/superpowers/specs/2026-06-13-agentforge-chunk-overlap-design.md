# AgentForge — 청킹 overlap (검색 substrate 개선) 설계

- 날짜: 2026-06-13
- 상태: 승인됨 (사용자가 자율 진행 위임 — 설계 승인 게이트 생략)
- 동기: 현 청커는 heading/문단 블록 단위로 잘되어 있으나 **overlap이 0**이고 작은 문단이 각각 미니 청크가 된다. 근거가 청크 경계에서 분산되어 검색 recall 저하. rag-design은 target≈650토큰·overlap 80~120·split 우선순위(heading>paragraph>sentence>token)를 이미 규정.

## 1. 결정 (approach B: heading 구간 내 어절-윈도우 + overlap)
- **순수 flat sliding window(approach C) 기각**: heading/section_path/line locator를 잃어 인용 품질 회귀, rag-design split 우선순위 위반.
- **intra-block만(approach A) 기각**: 인접 짧은 문단이 경계를 가로지르는 흔한 케이스를 해결 못 함.
- **채택 B**: **heading 구간을 절대 넘지 않는** 어절(whitespace word) 윈도우로 누적·overlap. heading 경계 = 가장 강한 구조 신호라 보존(section_path/citation 유지). 한 구간 내에서 어절을 `target_tokens`까지 모아 한 청크, 다음 청크는 `step = target - overlap` 만큼 전진(직전 청크 끝 `overlap_tokens` 어절을 다시 포함).

### 토큰 단위 — 정직한 프록시
- 정밀 토크나이저 도입은 범위 밖(YAGNI). 기존 프록시 `len(text.split())`(어절) 유지 — grounding.py와 동일 일관성.
- 한국어 1어절 ≈ subword 1.5~2.5토큰. 따라서 rag-design의 "650 subword 토큰"을 **어절 ≈ 320**, "overlap 80~120"을 **어절 ≈ 50**으로 환산해 기본값으로 둔다.
- **이 프록시 한계(어절≠subword)와, 로컬 toy 모델(qwen3:1.7b)의 eval 노이즈로 효과가 거칠게 보일 수 있음을 eval 결과 문서에 명시.** 운영 35B 재검 필요.

## 2. 알고리즘 (heading 구간 단위)
1. 기존대로 라인 순회하며 markdown heading으로 구간(section_path) 분리. blank line은 구간 내 구분자.
2. 각 구간에서 (어절, line_no) 평탄 리스트 구성(라인별 strip 후 공백 분할, line_no 추적).
3. 윈도우: `i`를 0부터 `step=max(1, target-overlap)` 간격으로 전진, 윈도우 = words[i : i+target].
   - `content = " ".join(window words)`, `line_start = 첫 어절 line_no`, `line_end = 마지막 어절 line_no`.
   - 마지막 윈도우가 구간 끝에 도달하면 종료(잔여가 overlap 이하로만 남으면 추가 청크 생성 안 함 — 중복 방지).
4. 구간이 어절 0개면 청크 없음.
5. `chunk_index`는 문서 전역 증가(현행 유지) → chunk_id 결정성 유지.

## 3. 계약 보존/변경
- **보존**: chunk_id 포맷(`{doc}:{ver}:l{start}-{end}:c{idx}:{locator_hash}`), section_path, citation_locator(line range 기반), content_hash/chunk_hash 계산식, ParsedChunk 필드, 결정성(동일 입력→동일 chunk_id).
- **의도적 변경**: 작은 문단이 target까지 **병합**되고 인접 청크가 **overlap**을 공유 → 청크 경계/개수/line range가 달라진다. 이는 슬라이스의 목적.
  - `test_plain_text_parser_is_deterministic`는 "문단=청크" 옛 동작을 단언 → **새 동작(병합 1청크, 결정성 유지)으로 갱신**.
  - `test_markdown_parser_preserves_heading_path_and_line_locator`는 heading 구간 경계가 유지되므로 **불변(통과)**.

## 4. 설정 (env)
- `app/core/config.py`: `chunk_target_tokens: int = 320`, `chunk_overlap_tokens: int = 50` (env `AGENT_FORGE_CHUNK_TARGET_TOKENS`/`_OVERLAP_TOKENS`). overlap < target 불변식(코드에서 clamp).
- `parse_txt_md_document`에 `target_tokens`/`overlap_tokens` 파라미터 추가(기본값 320/50, 하위호환 위해 `chunk_size`도 시그니처 유지하되 미사용/deprecated).
- `indexing.py`: `get_settings()`로 기본값, `job.config.chunking`이 있으면 override.
- `CHUNKER_VERSION` → `token-window-overlap-chunker/0.2.0`로 갱신(재색인 추적).

## 5. 검증
- pytest 풀스위트(.env 옆으로): 시작 baseline 측정 후 그린 + 신규 overlap 테스트. 실제 숫자 정직히 기록.
- 신규 단위테스트: (a) 다문단 body에서 경계 어절이 인접 청크 양쪽에 포함(overlap 입증), (b) accumulate-to-target(여러 작은 문단이 1청크로), (c) heading 경계 미초월, (d) 결정성, (e) target보다 큰 단일 구간이 step 간격으로 다중 청크.
- 라이브 eval: 깨끗한 eval DB로 cases-live-v0.1 재인제스트(청킹 변경=기존 청크 무효) → `run_live_eval.py` before/after. citation%/useful%/top_score 변화를 `docs/eval-results-live-v0.1.md`에 기록(프록시·toy모델 한계 명시).
- 보안 영향 없음(인덱싱 경로만, ACL/payload 불변).

## 6. 영향 파일
`app/core/config.py`(필드 2), `app/domain/parsers.py`(어절-윈도우 청킹 + CHUNKER_VERSION), `app/domain/indexing.py`(설정 배선), `apps/api/tests/test_parser_contracts.py`(plain-text 갱신 + overlap 테스트), `docs/eval-results-live-v0.1.md`(before/after).

## 7. 범위 밖 (후속)
표/구조 단위 청킹(table=1청크), paragraph-우선 패킹(현재는 heading>token), 정밀 토크나이저, page-level locator.
