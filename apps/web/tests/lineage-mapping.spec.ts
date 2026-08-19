import { expect, test } from "@playwright/test";

import {
  HEADING_DETECTION_UNAVAILABLE,
  LOW_TEXT_DENSITY,
  NO_HEADINGS_DETECTED,
  lineageDetail,
  lineageLabel,
  lineageReason,
  lineageState,
  warningReason,
  type DocumentIngestion,
  type LineageState,
} from "../app/lib/lineage";

// AC-04: the reason shown maps from the code the BACKEND recorded, and the console derives no
// verdict of its own. This spec needs no browser and no server -- it exercises the mapping
// directly, so a wrong mapping fails here with a readable diff instead of as a mystery
// assertion inside a page test.
//
// Every fixture below is the shape of a row that actually exists in the demo database
// (checked against document_ingestions on 2026-08-14: 36 observed-structured rows, 8 observed
// -collapsed DOCX rows, 34 backfilled 'unknown' rows, and 2 documents with no row at all).

const BASE: DocumentIngestion = {
  id: "ing-1",
  document_id: "doc-1",
  index_job_id: "job-1",
  extraction_status: "ok",
  source_mime_type: "text/markdown",
  converted_mime_type: "text/markdown",
  converter_chain: "inline/1>text/markdown",
  chunk_count: 4,
  structured_chunk_count: 4,
  extracted_char_count: 900,
  source_unit_kind: "line",
  source_unit_count: 40,
  warnings: [],
  created_at: "2026-08-14T04:31:24.194361",
};

function row(overrides: Partial<DocumentIngestion> = {}): DocumentIngestion {
  return { ...BASE, ...overrides };
}

// An observed markdown ingestion: every chunk carried a section path.
const STRUCTURED = row();

// An observed DOCX ingestion: handed to the chunker as text/plain, one chunk, no section path.
const COLLAPSED = row({
  source_mime_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  converted_mime_type: "text/plain",
  converter_chain: "python-docx/1.2.0>text/plain",
  chunk_count: 1,
  structured_chunk_count: 0,
  warnings: [HEADING_DETECTION_UNAVAILABLE, NO_HEADINGS_DETECTED],
});

// A row written by migration 0007's backfill: chunk counts were derivable from rows that
// already existed, the conversion was never observed, so extraction_status is 'unknown'.
const BACKFILLED = row({
  index_job_id: null,
  extraction_status: "unknown",
  converted_mime_type: null,
  converter_chain: null,
  extracted_char_count: null,
  source_unit_kind: null,
  source_unit_count: null,
  warnings: [],
});

const FAILED = row({
  extraction_status: "failed",
  converted_mime_type: null,
  converter_chain: null,
  chunk_count: null,
  structured_chunk_count: null,
  extracted_char_count: null,
  warnings: [],
});

test.describe("lineage state mapping", () => {
  test("an observed ingestion whose chunks carried section paths is structured", () => {
    expect(lineageState(STRUCTURED)).toBe("structured");
    expect(lineageLabel(lineageState(STRUCTURED))).toBe("구조 인식됨");
    expect(lineageReason(STRUCTURED)).toBe("제목 구조가 인용에 반영되었습니다.");
  });

  test("an ingestion the backend flagged for structure loss is collapsed", () => {
    expect(lineageState(COLLAPSED)).toBe("collapsed");
    expect(lineageLabel(lineageState(COLLAPSED))).toBe("구조 유실");
    // Both recorded codes are shown; neither is dropped.
    expect(lineageReason(COLLAPSED)).toContain("제목 구조를 인식할 수 없는 형식으로 변환되었습니다.");
    expect(lineageReason(COLLAPSED)).toContain("감지된 제목이 없어 인용이 본문 줄 번호로만 남습니다.");
  });

  test("a document with no ingestion row at all is unknown, never healthy", () => {
    for (const missing of [null, undefined]) {
      expect(lineageState(missing)).toBe("unknown");
      expect(lineageLabel(lineageState(missing))).toBe("구조 정보 없음");
      expect(lineageReason(missing)).toBe("색인 기록이 없습니다.");
      expect(lineageDetail(missing)).toBe("");
    }
  });

  test("a backfilled row is unknown EVEN THOUGH its chunk counts look structured", () => {
    // The regression this ordering exists to prevent: 34 rows in the demo database carry
    // structured_chunk_count === chunk_count with extraction_status 'unknown'. Testing the
    // counts before the status would render every one of them as healthy, asserting the exact
    // verification the backfill refused to claim.
    expect(BACKFILLED.structured_chunk_count).toBe(4);
    expect(lineageState(BACKFILLED)).toBe("unknown");
    expect(lineageReason(BACKFILLED)).toBe(
      "계측 도입 전에 색인되어 변환 품질이 기록되지 않았습니다.",
    );
  });

  test("a backfilled row with zero structured chunks is unknown, not collapsed", () => {
    // The counts say the chunks carry no section path, and they are shown verbatim in the
    // detail line. The STATE still says unknown, because the backfill recorded no warning and
    // the console does not raise one on the backend's behalf.
    const collapsedLookingBackfill = row({
      extraction_status: "unknown",
      converted_mime_type: null,
      chunk_count: 1,
      structured_chunk_count: 0,
      warnings: [],
    });
    expect(lineageState(collapsedLookingBackfill)).toBe("unknown");
    expect(lineageDetail(collapsedLookingBackfill)).toBe("청크 1개 중 구조 인식 0개");
  });

  test("a failed attempt is reported as failed, not as an absence of lineage", () => {
    expect(lineageState(FAILED)).toBe("failed");
    expect(lineageLabel(lineageState(FAILED))).toBe("추출 실패");
    expect(lineageReason(FAILED)).toBe("마지막 색인 시도가 실패로 기록되었습니다.");
  });

  test("an observed attempt that produced no chunks claims nothing about structure", () => {
    const nothingProduced = row({ chunk_count: 0, structured_chunk_count: 0, warnings: [] });
    expect(lineageState(nothingProduced)).toBe("unknown");
    // 0 was OBSERVED, so it gets its own sentence rather than "not recorded".
    expect(lineageReason(nothingProduced)).toBe("청크가 생성되지 않아 인용할 구간이 없습니다.");
  });

  test("every state has a distinct label", () => {
    const states: LineageState[] = ["structured", "collapsed", "failed", "unknown"];
    const labels = states.map(lineageLabel);
    expect(new Set(labels).size).toBe(states.length);
  });
});

test.describe("recorded codes and counts", () => {
  test("each recorded warning code maps to its own phrase", () => {
    expect(warningReason(HEADING_DETECTION_UNAVAILABLE)).toBe(
      "제목 구조를 인식할 수 없는 형식으로 변환되었습니다.",
    );
    expect(warningReason(NO_HEADINGS_DETECTED)).toBe(
      "감지된 제목이 없어 인용이 본문 줄 번호로만 남습니다.",
    );
    expect(warningReason(LOW_TEXT_DENSITY)).toBe("페이지당 추출된 문자 수가 적습니다.");
  });

  test("a code this console does not know is shown verbatim, not swallowed", () => {
    expect(warningReason("SOME_FUTURE_CODE")).toBe("기록된 코드: SOME_FUTURE_CODE");
    const future = row({ warnings: ["SOME_FUTURE_CODE"] });
    expect(lineageReason(future)).toContain("SOME_FUTURE_CODE");
    // And it is NOT certified as structured despite counts that look fine: a green badge
    // beside an unexplained warning is precisely the display this Work Order exists to stop.
    expect(future.structured_chunk_count).toBe(4);
    expect(lineageState(future)).toBe("unknown");
  });

  test("counts are shown verbatim and a NULL count is omitted rather than printed as 0", () => {
    expect(lineageDetail(STRUCTURED)).toBe("청크 4개 중 구조 인식 4개 · 청커 입력 text/markdown");
    expect(lineageDetail(COLLAPSED)).toBe("청크 1개 중 구조 인식 0개 · 청커 입력 text/plain");
    // NOT OBSERVED must never surface as a number.
    expect(lineageDetail(FAILED)).toBe("");
    expect(lineageDetail(BACKFILLED)).toBe("청크 4개 중 구조 인식 4개");
  });

  test("no state renders a score, grade or percentage", () => {
    for (const ingestion of [STRUCTURED, COLLAPSED, BACKFILLED, FAILED, null]) {
      const rendered = `${lineageLabel(lineageState(ingestion))} ${lineageReason(ingestion)} ${lineageDetail(ingestion)}`;
      expect(rendered).not.toMatch(/[%]|점수|등급|품질\s*점/);
    }
  });
});
