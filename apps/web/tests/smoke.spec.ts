import { expect, test, type Page } from "@playwright/test";

const routes = [
  { path: "/", heading: "Agent readiness control" },
  { path: "/agents", heading: "Agents" },
  { path: "/knowledge", heading: "Knowledge" },
  { path: "/eval", heading: "Evaluation" },
  { path: "/trace", heading: "Trace Viewer" },
  { path: "/audit", heading: "Audit" },
  { path: "/admin/settings", heading: "Settings" },
];

async function mockRuntimeTrace(page: Page, runId = "runtime-1") {
  await page.route(`**/api/v1/runs/${runId}`, async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        id: runId,
        status: "succeeded",
        latency_ms: 412,
        retrieval_denied_count: 1,
        citations: [
          {
            document_id: "FIN-001",
            title: "Expense Reimbursement Policy",
            citation_locator: "section:receipt-deadline",
          },
        ],
        guardrail: {
          outcome: "answer",
          model_route_summary: {
            answer_generator: { tier: "standard-rag" },
          },
        },
      },
    });
  });

  await page.route(`**/api/v1/runs/${runId}/steps`, async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: [
        {
          step_type: "retriever",
          status: "succeeded",
          latency_ms: 34,
          input_summary: { top_k: 5 },
          output_summary: {
            route_stage: "retriever",
            model_tier: "deterministic",
            hit_count: 2,
            denied_count: 1,
          },
        },
        {
          step_type: "generator",
          status: "succeeded",
          latency_ms: 118,
          input_summary: { context_count: 1 },
          output_summary: {
            route_stage: "answer_generator",
            model_tier: "standard-rag",
            citation_count: 1,
          },
        },
      ],
    });
  });

  await page.route(`**/api/v1/runs/${runId}/retrieval-hits`, async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: [
        {
          id: "hit-1",
          document_id: "FIN-001",
          chunk_id: "fin-001-1",
          title: "Expense Reimbursement Policy",
          citation_locator: "section:receipt-deadline",
          rank_original: 1,
          score_vector: 0.94,
          used_in_context: true,
          used_as_citation: true,
          acl_filter_snapshot: { subjects: ["department:Finance"] },
        },
        {
          id: "hit-2",
          document_id: "FIN-002",
          chunk_id: "fin-002-1",
          title: "Quarter Close Restricted Checklist",
          citation_locator: "section:exception-ledger",
          rank_original: 2,
          score_vector: 0.71,
          used_in_context: true,
          used_as_citation: false,
          acl_filter_snapshot: { subjects: ["department:Finance"] },
        },
      ],
    });
  });
}

test.describe("Agent Studio shell", () => {
  for (const route of routes) {
    test(`renders ${route.path}`, async ({ page }) => {
      await page.goto(route.path);
      await expect(page.getByRole("heading", { name: route.heading, exact: true })).toBeVisible();
      await expect(page.getByRole("link", { name: "Agent Forge" })).toBeVisible();
    });
  }

  test("operator can navigate from overview to core workspaces", async ({ page }) => {
    await page.goto("/");

    const primaryNav = page.getByLabel("Primary");

    await primaryNav.getByRole("link", { name: "Agents", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Agents", exact: true })).toBeVisible();
    await expect(primaryNav.getByRole("link", { name: "Agents", exact: true })).toHaveAttribute(
      "aria-current",
      "page",
    );

    await primaryNav.getByRole("link", { name: "Knowledge", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Knowledge", exact: true })).toBeVisible();

    await primaryNav.getByRole("link", { name: "Audit", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Audit", exact: true })).toBeVisible();
  });

  test("knowledge flow supports local upload, index queue, and retrieval preview", async ({ page }) => {
    await page.route("**/api/**", async (route) => {
      await route.fulfill({ status: 404, body: "Not found" });
    });

    await page.goto("/knowledge");

    await expect(page.getByRole("heading", { name: "Knowledge", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: /Policy library/ })).toBeVisible();

    await page.getByLabel("Document title").fill("Q2 support policy addendum");
    await page.getByLabel("Checksum").fill("sha256:test-addendum");
    await page.getByRole("button", { name: "Upload document" }).click();

    await expect(page.getByText("Q2 support policy addendum", { exact: true })).toBeVisible();
    await expect(page.getByText(/Registered Q2 support policy addendum locally/)).toBeVisible();

    await page.getByRole("button", { name: "Queue index" }).click();
    await expect(page.getByText(/Queued .* document\(s\) locally/)).toBeVisible();

    await page.getByLabel("Question").fill("How should refund exceptions be answered?");
    await page.getByRole("button", { name: "Preview retrieval" }).click();

    await expect(page.getByText(/Retrieval preview is using local ranking/)).toBeVisible();
    await expect(
      page.locator(".retrievalResults").getByText("Refund exception policy", { exact: true }).first(),
    ).toBeVisible();
  });

  test("uploaded knowledge evidence can be traced through runtime review", async ({ page }) => {
    await page.route("**/api/v1/knowledge/sources", async (route) => {
      if (route.request().method() !== "GET") {
        await route.fallback();
        return;
      }

      await route.fulfill({
        contentType: "application/json",
        json: [
          {
            id: "source-upload-1",
            name: "Uploaded policy source",
            owner_department: "Operations",
            default_confidentiality_level: "internal",
            status: "active",
            updated_at: "2026-05-15T00:00:00Z",
          },
        ],
      });
    });
    await page.route("**/api/v1/knowledge/documents", async (route) => {
      if (route.request().method() !== "GET") {
        await route.fallback();
        return;
      }

      await route.fulfill({ contentType: "application/json", json: [] });
    });
    await page.route("**/api/v1/knowledge/documents/upload?**", async (route) => {
      await route.fulfill({
        contentType: "application/json",
        json: {
          id: "uploaded-doc-1",
          knowledge_source_id: "source-upload-1",
          title: "Uploaded remote work policy",
          object_uri: "object://agent-forge-documents/knowledge/source-upload-1/uploaded-doc-1.md",
          checksum: "sha256-uploaded",
          mime_type: "text/markdown",
          confidentiality_level: "internal",
          access_groups: ["all-employees"],
          status: "registered",
          effective_date: "2026-05-15",
          created_at: "2026-05-15T00:00:00Z",
          updated_at: "2026-05-15T00:00:00Z",
        },
      });
    });
    await page.route("**/api/v1/knowledge/documents/uploaded-doc-1/index-jobs", async (route) => {
      await route.fulfill({
        contentType: "application/json",
        json: {
          id: "index-job-1",
          document_id: "uploaded-doc-1",
          status: "succeeded",
          stage: "upsert",
          config: { source: "object_store" },
          created_by: "operator",
          chunk_count: 1,
          error_code: null,
          error_message: null,
          artifact_uri: "db://document_chunks/uploaded-doc-1",
          started_at: "2026-05-15T00:00:00Z",
          finished_at: "2026-05-15T00:00:01Z",
          created_at: "2026-05-15T00:00:00Z",
          updated_at: "2026-05-15T00:00:01Z",
        },
      });
    });
    await page.route("**/api/v1/knowledge/retrieval/preview", async (route) => {
      await route.fulfill({
        contentType: "application/json",
        json: {
          query: "manager approval",
          denied_count: 0,
          hits: [
            {
              document_id: "uploaded-doc-1",
              knowledge_source_id: "source-upload-1",
              chunk_id: "uploaded-chunk-1",
              title: "Uploaded remote work policy",
              confidentiality_level: "internal",
              access_groups: ["all-employees"],
              score: 0.92,
              citation: "Uploaded remote work policy / Eligibility / lines 7-7",
              citation_locator: "Uploaded remote work policy / Eligibility / lines 7-7",
            },
          ],
        },
      });
    });

    await page.goto("/knowledge");
    await page.getByRole("button", { name: "Sync API" }).click();
    await expect(page.getByRole("button", { name: /Uploaded policy source/ })).toBeVisible();

    await page.getByLabel("Document title").fill("Uploaded remote work policy");
    await page.setInputFiles('input[type="file"]', {
      name: "remote-work.md",
      mimeType: "text/markdown",
      buffer: Buffer.from("# Remote Work\n\n## Eligibility\n\nEmployees may request remote work."),
    });
    await page.getByRole("button", { name: "Upload document" }).click();
    await expect(page.getByText("Uploaded remote work policy", { exact: true })).toBeVisible();
    await expect(page.getByText(/Registered Uploaded remote work policy through/)).toBeVisible();

    await page.getByRole("button", { name: "Queue index" }).click();
    await expect(page.getByText(/Indexed uploaded object storage document/)).toBeVisible();

    await page.getByLabel("Question").fill("manager approval");
    await page.getByRole("button", { name: "Preview retrieval" }).click();
    await expect(
      page.locator(".retrievalResults").getByText("Uploaded remote work policy", { exact: true }),
    ).toBeVisible();

    await page.route("**/api/v1/eval/overview", async (route) => {
      await route.fulfill({
        contentType: "application/json",
        json: {
          run: {
            id: "eval-upload-1",
            corpus_id: "upload-to-runtime-smoke",
            mode: "api",
            status: "passed",
            total_cases: 1,
            passed_cases: 1,
            failed_cases: 0,
            summary: {
              citation_coverage: 1,
              trace_completeness: 1,
              acl_violation_count: 0,
            },
          },
          suite_counts: { citation: 1 },
          results: [
            {
              case_id: "upload_trace_001",
              suite: "citation",
              expected_behavior: "answer",
              passed: true,
              run_id: "runtime-upload-1",
              status: "succeeded",
              citation_document_ids: ["uploaded-doc-1"],
              retrieval_document_ids: ["uploaded-doc-1"],
              retrieval_denied_count: 0,
              findings: [],
            },
          ],
        },
      });
    });
    await page.route("**/api/v1/runs/runtime-upload-1", async (route) => {
      await route.fulfill({
        contentType: "application/json",
        json: {
          id: "runtime-upload-1",
          status: "succeeded",
          latency_ms: 331,
          retrieval_denied_count: 0,
          citations: [
            {
              document_id: "uploaded-doc-1",
              chunk_id: "uploaded-chunk-1",
              title: "Uploaded remote work policy",
              citation_locator: "Uploaded remote work policy / Eligibility / lines 7-7",
              score: 0.92,
            },
          ],
          guardrail: {
            outcome: "answer",
            model_route_summary: {
              answer_generator: { tier: "standard-rag" },
            },
          },
        },
      });
    });
    await page.route("**/api/v1/runs/runtime-upload-1/steps", async (route) => {
      await route.fulfill({
        contentType: "application/json",
        json: [
          {
            step_type: "retriever",
            status: "succeeded",
            latency_ms: 28,
            input_summary: { top_k: 1 },
            output_summary: {
              route_stage: "retriever",
              model_tier: "deterministic",
              hit_count: 1,
              denied_count: 0,
            },
          },
          {
            step_type: "generator",
            status: "succeeded",
            latency_ms: 104,
            input_summary: { context_count: 1 },
            output_summary: {
              route_stage: "answer_generator",
              model_tier: "standard-rag",
              citation_count: 1,
            },
          },
        ],
      });
    });
    await page.route("**/api/v1/runs/runtime-upload-1/retrieval-hits", async (route) => {
      await route.fulfill({
        contentType: "application/json",
        json: [
          {
            id: "hit-upload-1",
            document_id: "uploaded-doc-1",
            chunk_id: "uploaded-chunk-1",
            title: "Uploaded remote work policy",
            citation_locator: "Uploaded remote work policy / Eligibility / lines 7-7",
            rank_original: 1,
            score_vector: 0.92,
            used_in_context: true,
            used_as_citation: true,
            acl_filter_snapshot: { subjects: ["all-employees"] },
          },
        ],
      });
    });

    await page.goto("/eval");
    await page.getByRole("button", { name: "Sync API" }).click();
    await expect(page.getByText(/Synced latest eval run/)).toBeVisible();
    await page.getByRole("button", { name: "Sync trace" }).click();
    await expect(page.getByText(/Synced runtime trace for upload_trace_001/)).toBeVisible();
    await expect(page.locator(".citationSection").getByText("Uploaded remote work policy").first()).toBeVisible();
    await expect(page.getByRole("link", { name: "Open trace" })).toHaveAttribute(
      "href",
      "/trace?run_id=runtime-upload-1",
    );

    await page.goto("/trace?run_id=runtime-upload-1");
    await expect(page.getByText(/Loaded runtime trace/)).toBeVisible();
    await expect(page.getByText("Uploaded remote work policy").first()).toBeVisible();
    await expect(page.getByText("Used as citation")).toBeVisible();
  });

  test("eval workflow supports suite filtering and trace citation review", async ({ page }) => {
    await page.route("**/api/**", async (route) => {
      await route.fulfill({ status: 404, body: "Not found" });
    });

    await page.goto("/eval");

    await expect(page.getByRole("heading", { name: "Evaluation", exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Synthetic corpus suites" })).toBeVisible();
    await expect(page.getByText(/Eval reports are persisted through \/api\/v1\/eval/)).toBeVisible();

    await page.getByRole("button", { name: "Sync API" }).click();
    await expect(page.getByText(/Persisted eval report unavailable/)).toBeVisible();

    await page.getByRole("button", { name: /Citation integrity/ }).click();
    await page.getByRole("button", { name: /cit_003/ }).click();

    await expect(page.getByRole("heading", { name: "Trace and citations" })).toBeVisible();
    await expect(page.getByText(/Matched expected answer path/)).toBeVisible();
    await expect(page.locator(".citationSection").getByText("Expense Reimbursement Policy").first()).toBeVisible();
    await expect(page.getByText("citation_validator")).toBeVisible();

    await page.getByRole("button", { name: "Sync trace" }).click();
    await expect(page.getByText(/Runtime trace unavailable/)).toBeVisible();
  });

  test("eval trace sync renders step payloads and retrieval comparison", async ({ page }) => {
    await page.route("**/api/v1/eval/overview", async (route) => {
      await route.fulfill({
        contentType: "application/json",
        json: {
          run: {
            id: "eval-live-1",
            corpus_id: "synthetic-corpus-v0.1",
            mode: "api",
            status: "passed",
            total_cases: 1,
            passed_cases: 1,
            failed_cases: 0,
            summary: {
              citation_coverage: 1,
              trace_completeness: 1,
              acl_violation_count: 0,
            },
          },
          suite_counts: { citation: 1 },
          results: [
            {
              case_id: "cit_003",
              suite: "citation",
              expected_behavior: "answer",
              passed: true,
              run_id: "runtime-1",
              status: "succeeded",
              citation_document_ids: ["FIN-001"],
              retrieval_document_ids: ["FIN-001"],
              retrieval_denied_count: 1,
              findings: [],
            },
          ],
        },
      });
    });

    await mockRuntimeTrace(page);

    await page.goto("/eval");
    await page.getByRole("button", { name: "Sync API" }).click();
    await expect(page.getByText(/Synced latest eval run/)).toBeVisible();

    await page.getByRole("button", { name: "Sync trace" }).click();
    await expect(page.getByText(/Synced runtime trace for cit_003/)).toBeVisible();
    await expect(page.getByRole("link", { name: "Open trace" })).toHaveAttribute(
      "href",
      "/trace?run_id=runtime-1",
    );
    await expect(page.getByText(/route stage answer_generator/)).toBeVisible();
    await expect(page.getByText("Used as citation")).toBeVisible();
    await expect(page.getByText("Context only")).toBeVisible();

    await page.locator(".traceStep").filter({ hasText: "generator" }).getByText("Payload").click();
    await expect(page.getByText("context_count")).toBeVisible();
  });

  test("trace viewer opens a shareable runtime run URL", async ({ page }) => {
    await mockRuntimeTrace(page);

    await page.goto("/trace?run_id=runtime-1");

    await expect(page.getByRole("heading", { name: "Trace Viewer", exact: true })).toBeVisible();
    await expect(page.getByLabel("Run ID")).toHaveValue("runtime-1");
    await expect(page.getByText(/Loaded runtime trace/)).toBeVisible();
    await expect(page.getByText(/route stage answer_generator/)).toBeVisible();
    await expect(page.getByText("Used as citation")).toBeVisible();
    await expect(page.getByText("Context only")).toBeVisible();

    await page.locator(".traceStep").filter({ hasText: "generator" }).getByText("Payload").click();
    await expect(page.getByText("context_count")).toBeVisible();
  });

  test("audit page exposes queryable audit explorer shell", async ({ page }) => {
    await page.goto("/audit");

    await expect(page.getByRole("heading", { name: "Audit", exact: true })).toBeVisible();
    await expect(page.getByText("Audit API", { exact: true })).toBeVisible();
    await expect(page.locator(".timeline").getByText("eval_run.created", { exact: true })).toBeVisible();
    await expect(page.getByLabel("Event type")).toBeVisible();
    await expect(page.getByRole("button", { name: "Sync audit" })).toBeVisible();
  });

  test("agent rows drive the selected governance detail panel", async ({ page }) => {
    await page.goto("/agents");

    await page.getByRole("button", { name: /Security Policy Assistant/ }).click();

    await expect(
      page.getByRole("heading", { name: "Security Policy Assistant", exact: true }),
    ).toBeVisible();
    await expect(page.getByText("Run ACL suite", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: /Security Policy Assistant/ })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  test("locked release policies expose real switch semantics", async ({ page }) => {
    await page.goto("/admin/settings");

    await expect(page.getByRole("switch", { name: "Citation required locked on" })).toBeChecked();
    await expect(page.getByRole("switch", { name: "ACL filter required locked on" })).toBeChecked();
  });

  test("mobile console layout avoids horizontal overflow", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/agents");

    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);

    expect(overflow).toBe(false);
  });
});
