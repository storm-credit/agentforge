import { expect, test } from "@playwright/test";

// AC-03: structured, collapsed and no-recorded-lineage render as three distinguishable
// states on the knowledge documents view, and a document with no lineage never renders as
// healthy.
//
// The three fixtures are built through the real API rather than mocked, so what the page
// renders is what the pipeline actually recorded. Each one's lineage was MEASURED before this
// spec was written (apps/api, in-memory client, 2026-08-14):
//
//   text/markdown + headings -> extraction_status ok, chunk 2 / structured 2, warnings []
//   text/plain               -> extraction_status ok, chunk 1 / structured 0,
//                               warnings [HEADING_DETECTION_UNAVAILABLE, NO_HEADINGS_DETECTED]
//   registered, never indexed -> no document_ingestions row at all -> ingestion null
//
// text/plain is used for the collapsed case instead of a DOCX because it reaches the SAME
// seam without a binary fixture: chunker_mime_type_for leaves it as text/plain, which is not
// a heading-aware type, so the heading detector never runs — exactly what happens to every
// PDF and DOCX today.
const API_BASE = process.env.PLAYWRIGHT_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";

const ADMIN = {
  "X-Agent-Forge-User": "e2e-lineage-operator",
  "X-Agent-Forge-Department": "Operations",
  "X-Agent-Forge-Roles": "admin",
  "X-Agent-Forge-Groups": "all-employees",
  "X-Agent-Forge-Clearance": "internal",
};

const MARKDOWN_WITH_HEADINGS = [
  "# 취업규칙",
  "",
  "## 제3장 휴가",
  "연차 휴가는 15일이다.",
  "",
  "## 제4장 근무",
  "근무 시간은 8시간이다.",
  "",
].join("\n");

test("the knowledge list distinguishes structured, collapsed and unrecorded lineage", async ({
  page,
  request,
}) => {
  test.setTimeout(120_000);
  const stamp = Date.now();
  const titles = {
    structured: `Lineage Structured ${stamp}`,
    collapsed: `Lineage Collapsed ${stamp}`,
    none: `Lineage Unrecorded ${stamp}`,
  };

  // Reuse an existing knowledge source rather than creating one. There is no delete-source
  // endpoint, so a per-run source would accumulate forever, and it would also become the
  // newest source -- which is what knowledge-archive/demo-role pick with
  // `selectOption({ index: 1 })`.
  const existing = await request.get(`${API_BASE}/knowledge/sources`, { headers: ADMIN });
  expect(existing.status()).toBe(200);
  const sources = await existing.json();
  // The e2e backend is seeded (app.seed_demo) before the suite runs, so this is a setup
  // assertion, not a product one.
  expect(sources.length).toBeGreaterThan(0);
  const sourceId = sources[0].id;

  async function register(title: string, mimeType: string): Promise<string> {
    const created = await request.post(`${API_BASE}/knowledge/documents`, {
      headers: ADMIN,
      data: {
        knowledge_source_id: sourceId,
        title,
        object_uri: `inline://${title}`,
        checksum: `sha256-${title}`,
        mime_type: mimeType,
        confidentiality_level: "internal",
        access_groups: ["all-employees"],
      },
    });
    expect(created.status()).toBe(201);
    return (await created.json()).id;
  }

  async function index(documentId: string) {
    const job = await request.post(`${API_BASE}/knowledge/documents/${documentId}/index-jobs`, {
      headers: ADMIN,
      data: { source_text: MARKDOWN_WITH_HEADINGS },
    });
    expect(job.status()).toBe(201);
    expect((await job.json()).status).toBe("succeeded");
  }

  const structuredId = await register(titles.structured, "text/markdown");
  const collapsedId = await register(titles.collapsed, "text/plain");
  const unrecordedId = await register(titles.none, "text/markdown");
  await index(structuredId);
  await index(collapsedId);
  // titles.none is deliberately NOT indexed: no attempt, so no lineage row.

  try {
    await page.goto("/knowledge");
    await expect(page.getByRole("heading", { name: "지식 문서", level: 1 })).toBeVisible();

    const row = (title: string) => page.getByTestId("doc-row").filter({ hasText: title });
    for (const title of Object.values(titles)) {
      await expect(row(title)).toBeVisible({ timeout: 15_000 });
    }

    // --- structured -------------------------------------------------------------------
    const structured = row(titles.structured);
    await expect(structured.getByTestId("doc-lineage")).toHaveAttribute(
      "data-lineage-state",
      "structured",
    );
    await expect(structured.getByTestId("doc-lineage")).toHaveText("구조 인식됨");
    await expect(structured.getByTestId("doc-lineage-reason")).toHaveText(
      "제목 구조가 인용에 반영되었습니다.",
    );
    await expect(structured.getByTestId("doc-lineage-detail")).toContainText("구조 인식 2개");

    // --- collapsed --------------------------------------------------------------------
    const collapsed = row(titles.collapsed);
    await expect(collapsed.getByTestId("doc-lineage")).toHaveAttribute(
      "data-lineage-state",
      "collapsed",
    );
    await expect(collapsed.getByTestId("doc-lineage")).toHaveText("구조 유실");
    // The reason is the code the BACKEND recorded, not a judgement made here.
    await expect(collapsed.getByTestId("doc-lineage-reason")).toContainText(
      "감지된 제목이 없어 인용이 본문 줄 번호로만 남습니다.",
    );
    await expect(collapsed.getByTestId("doc-lineage-detail")).toContainText(
      "청크 1개 중 구조 인식 0개",
    );

    // --- no recorded lineage ----------------------------------------------------------
    const unrecorded = row(titles.none);
    await expect(unrecorded.getByTestId("doc-lineage")).toHaveAttribute(
      "data-lineage-state",
      "unknown",
    );
    await expect(unrecorded.getByTestId("doc-lineage")).toHaveText("구조 정보 없음");
    await expect(unrecorded.getByTestId("doc-lineage-reason")).toHaveText("색인 기록이 없습니다.");
    // It must not borrow the healthy state's wording, and it has no counts to show.
    await expect(unrecorded.getByTestId("doc-lineage")).not.toHaveText("구조 인식됨");
    await expect(unrecorded.getByTestId("doc-lineage-detail")).toHaveCount(0);

    // --- the three states are actually distinguishable from one another ----------------
    const states = await Promise.all(
      Object.values(titles).map((title) =>
        row(title).getByTestId("doc-lineage").getAttribute("data-lineage-state"),
      ),
    );
    expect(new Set(states).size).toBe(3);
    const labels = await Promise.all(
      Object.values(titles).map((title) => row(title).getByTestId("doc-lineage").innerText()),
    );
    expect(new Set(labels).size).toBe(3);

    // --- informational only (AC-05) ---------------------------------------------------
    // No state hides a row or removes a control: the collapsed document is still listed and
    // still fully operable.
    await expect(collapsed.getByTestId("acl-edit")).toBeVisible();
    await expect(collapsed.getByTestId("archive-doc")).toBeVisible();
  } finally {
    // Repeated runs against the same backend must not accumulate rows.
    for (const id of [structuredId, collapsedId, unrecordedId]) {
      await request.delete(
        `${API_BASE}/knowledge/documents/${id}?reason=lineage+e2e+cleanup`,
        { headers: ADMIN },
      );
    }
  }
});
