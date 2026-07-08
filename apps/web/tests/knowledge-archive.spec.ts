import { test, expect } from "@playwright/test";

// Requires the API + a seeded knowledge source running behind the dev server.
// Creates its own document (rather than touching a "first row" seeded doc) so it
// does not disturb other specs running in parallel against the same backend.
test("archiving a document via the knowledge page removes it from the list", async ({ page }) => {
  await page.goto("/knowledge");
  await expect(page.getByRole("heading", { name: "Knowledge" })).toBeVisible();

  const uniqueTitle = `Archive Test Doc ${Date.now()}`;

  // Pick the first existing knowledge source (default "기존 선택" mode).
  const sourceSelect = page.getByTestId("source-select");
  await sourceSelect.selectOption({ index: 1 });

  await page.getByPlaceholder("문서 제목").fill(uniqueTitle);
  await page.getByPlaceholder(/본문/).fill("This is an e2e test document created for archive testing.");
  await expect(page.getByTestId("ingest")).toBeEnabled();
  await page.getByTestId("ingest").click();

  const newRow = page.getByTestId("doc-row").filter({ hasText: uniqueTitle });
  await expect(newRow).toBeVisible({ timeout: 15_000 });

  await newRow.getByTestId("archive-doc").click();
  await expect(newRow.getByTestId("archive-form")).toBeVisible();
  await newRow.getByTestId("archive-reason").fill("e2e archive test cleanup");
  await newRow.getByTestId("archive-confirm").click();

  await expect(page.getByTestId("doc-row").filter({ hasText: uniqueTitle })).toHaveCount(0);
});
