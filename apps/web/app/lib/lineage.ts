// Rendering the ingestion lineage the BACKEND recorded (WO-2026-08-14-LINEAGE-VISIBILITY-002).
//
// WHAT THIS FILE IS ALLOWED TO DO
//
// Look up recorded values and choose Korean copy for them. That is all. It computes no
// quality number, no score, no grade, no percentage, and it never re-derives a verdict the
// backend did not record — the backend owns that judgement (apps/api/app/domain/
// ingestion_lineage.py), and a second implementation here would eventually disagree with it.
//
// WHY THE ORDER OF THE CHECKS IN `lineageState` MATTERS MORE THAN THE CHECKS THEMSELVES
//
// A row backfilled by migration 0007 carries `extraction_status: "unknown"` together with
// REAL chunk counts, because the counts were derivable from rows that already existed and the
// conversion quality was not. So a backfilled markdown document can read
// `structured_chunk_count: 4, chunk_count: 4` while nobody ever observed its extraction. If
// the count test ran first, that document would render as healthy — asserting exactly the
// verification the backfill deliberately refused to claim. `unknown` is therefore checked
// BEFORE any count, and `test lineage-mapping.spec.ts` pins that ordering with a fixture
// built from a real row shape.
//
// A document with NO lineage row at all (`ingestion === null`) is a different fact again —
// nothing was ever attempted — and it also renders as unknown, never as healthy.

export type DocumentIngestion = {
  id: string;
  document_id: string;
  index_job_id: string | null;
  extraction_status: string;
  source_mime_type: string;
  converted_mime_type: string | null;
  converter_chain: string | null;
  chunk_count: number | null;
  structured_chunk_count: number | null;
  extracted_char_count: number | null;
  source_unit_kind: string | null;
  source_unit_count: number | null;
  warnings: string[];
  created_at: string;
};

// The four states an operator can be shown. `structured`, `collapsed` and `unknown` are the
// three the Work Order requires; `failed` exists because the backend records
// `extraction_status: "failed"` as a distinct value, and folding it into "no recorded
// lineage" would say nothing was recorded about a document whose failure WAS recorded.
export type LineageState = "structured" | "collapsed" | "failed" | "unknown";

// Warning codes as written by apps/api/app/domain/ingestion_lineage.py.
export const HEADING_DETECTION_UNAVAILABLE = "HEADING_DETECTION_UNAVAILABLE";
export const NO_HEADINGS_DETECTED = "NO_HEADINGS_DETECTED";
export const LOW_TEXT_DENSITY = "LOW_TEXT_DENSITY";

const EXTRACTION_FAILED = "failed";
const EXTRACTION_UNKNOWN = "unknown";

export function lineageState(ingestion: DocumentIngestion | null | undefined): LineageState {
  // 1. Nothing recorded at all.
  if (!ingestion) return "unknown";
  // 2. Recorded as NOT OBSERVED (0007 backfill). Checked before any count — see the header.
  if (ingestion.extraction_status === EXTRACTION_UNKNOWN) return "unknown";
  // 3. Recorded as a failed attempt.
  if (ingestion.extraction_status === EXTRACTION_FAILED) return "failed";
  // 4. The backend's own structure-loss codes. Not re-derived from the counts: these are the
  //    conditions it decided to flag, so the console flags exactly those and no others.
  const warnings = ingestion.warnings ?? [];
  if (
    warnings.includes(NO_HEADINGS_DETECTED) ||
    warnings.includes(HEADING_DETECTION_UNAVAILABLE)
  ) {
    return "collapsed";
  }
  // 5. Flagged for something else. The console will not certify a document the pipeline
  //    raised a warning about, whether or not it recognises the code — the alternative is a
  //    green badge sitting next to an unexplained warning, which is the failure mode this
  //    whole Work Order exists to stop. The code itself is still shown, by `lineageReason`.
  //    Currently unreachable in practice: the only other code is LOW_TEXT_DENSITY, which is
  //    raised only for page-counted formats, and every one of those is converted to
  //    text/plain and therefore already caught by check 4.
  if (warnings.length > 0) return "unknown";
  // 6. Observed, unflagged, and at least one chunk carried a section path.
  if (ingestion.structured_chunk_count !== null && ingestion.structured_chunk_count > 0) {
    return "structured";
  }
  // 7. Observed but nothing to say about structure (counts absent, or zero chunks produced).
  return "unknown";
}

const STATE_LABELS: Record<LineageState, string> = {
  structured: "구조 인식됨",
  collapsed: "구조 유실",
  failed: "추출 실패",
  unknown: "구조 정보 없음",
};

const STATE_BADGE_CLASS: Record<LineageState, string> = {
  structured: "badge success",
  collapsed: "badge warn",
  failed: "badge danger",
  unknown: "badge",
};

// One phrase per recorded warning code. An unrecognised code is shown verbatim rather than
// dropped: a code this console has not been taught about is still something the pipeline
// recorded, and silently hiding it would be the console deciding what the operator may know.
const WARNING_REASONS: Record<string, string> = {
  [HEADING_DETECTION_UNAVAILABLE]: "제목 구조를 인식할 수 없는 형식으로 변환되었습니다.",
  [NO_HEADINGS_DETECTED]: "감지된 제목이 없어 인용이 본문 줄 번호로만 남습니다.",
  [LOW_TEXT_DENSITY]: "페이지당 추출된 문자 수가 적습니다.",
};

export function warningReason(code: string): string {
  return WARNING_REASONS[code] ?? `기록된 코드: ${code}`;
}

export function lineageReason(ingestion: DocumentIngestion | null | undefined): string {
  if (!ingestion) return "색인 기록이 없습니다.";
  if (ingestion.extraction_status === EXTRACTION_UNKNOWN) {
    return "계측 도입 전에 색인되어 변환 품질이 기록되지 않았습니다.";
  }
  if (ingestion.extraction_status === EXTRACTION_FAILED) {
    return "마지막 색인 시도가 실패로 기록되었습니다.";
  }
  const warnings = ingestion.warnings ?? [];
  if (warnings.length > 0) return warnings.map(warningReason).join(" ");
  if (ingestion.structured_chunk_count !== null && ingestion.structured_chunk_count > 0) {
    return "제목 구조가 인용에 반영되었습니다.";
  }
  // Zero is an OBSERVED count, so it gets its own sentence: saying the count was not recorded
  // when it was recorded as 0 would be the same category of error as the reverse.
  if (ingestion.chunk_count === 0) return "청크가 생성되지 않아 인용할 구간이 없습니다.";
  return "구조 청크 수가 기록되지 않았습니다.";
}

// Recorded counts, verbatim. NEVER a ratio, a percentage or a grade: the two numbers are
// shown side by side exactly as stored, and a count the backend left NULL (NOT OBSERVED) is
// omitted rather than printed as 0.
export function lineageDetail(ingestion: DocumentIngestion | null | undefined): string {
  if (!ingestion) return "";
  const parts: string[] = [];
  if (ingestion.chunk_count !== null && ingestion.structured_chunk_count !== null) {
    parts.push(`청크 ${ingestion.chunk_count}개 중 구조 인식 ${ingestion.structured_chunk_count}개`);
  }
  if (ingestion.converted_mime_type !== null) {
    parts.push(`청커 입력 ${ingestion.converted_mime_type}`);
  }
  return parts.join(" · ");
}

export function lineageLabel(state: LineageState): string {
  return STATE_LABELS[state];
}

export function lineageBadgeClass(state: LineageState): string {
  return STATE_BADGE_CLASS[state];
}
