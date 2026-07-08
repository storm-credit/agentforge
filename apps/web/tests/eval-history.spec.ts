import { expect, test } from "@playwright/test";

// The eval page reads persisted eval-harness runs (GET /api/v1/eval/runs). A real
// live eval run needs the full LLM stack and minutes of wall time, so the test seeds
// one run directly via the privileged write endpoint with a minimal synthetic report
// (same shape the harness's aggregate() produces) and asserts the page renders it.
const API_BASE = process.env.PLAYWRIGHT_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";

const OPERATOR = {
  "X-Agent-Forge-User": "e2e-operator",
  "X-Agent-Forge-Department": "Operations",
  "X-Agent-Forge-Roles": "admin",
  "X-Agent-Forge-Groups": "all-employees",
  "X-Agent-Forge-Clearance": "internal",
};

test("eval page lists a persisted eval run with its headline metrics", async ({ page, request }) => {
  const label = `e2e-seed-${Date.now()}`;
  const created = await request.post(`${API_BASE}/eval/runs`, {
    headers: OPERATOR,
    data: {
      corpus_id: "e2e-corpus",
      label,
      report: {
        total: 2,
        citation_pct: 100.0,
        useful_answer_pct: 50.0,
        refusal_discipline_pct: 100.0,
        faithfulness_pct: null,
        corpus_id: "e2e-corpus",
        cases: [
          { case_id: "c1", citation_ok: true },
          { case_id: "c2", citation_ok: true },
        ],
      },
    },
  });
  expect(created.status()).toBe(201);

  await page.goto("/eval");
  // Keep parity with smoke.spec.ts: the heading must stay "Evaluation".
  await expect(page.getByRole("heading", { name: "Evaluation", exact: true })).toBeVisible();

  const row = page.getByTestId("eval-run-row").filter({ hasText: label });
  await expect(row).toBeVisible();
  await expect(row).toContainText("e2e-corpus");
  await expect(row).toContainText("100.0%"); // citation_pct
  await expect(row).toContainText("50.0%"); // useful_answer_pct
  await expect(row).toContainText("—"); // faithfulness_pct null renders as em-dash
  // No empty state once at least one run exists.
  await expect(page.getByTestId("eval-empty")).toHaveCount(0);
});
