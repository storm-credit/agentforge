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

// Archived-view toggle + restore flow. Requires the backend's admin-only
// include_archived flag on GET /documents (PR #68) and POST .../restore (PR #55).
test("archived view toggle surfaces archived docs (admin only) and restore returns them", async ({ page }) => {
  test.setTimeout(120_000);
  await page.goto("/knowledge");
  await expect(page.getByRole("heading", { name: "Knowledge" })).toBeVisible();

  const uniqueTitle = `Restore Test Doc ${Date.now()}`;
  const row = () => page.getByTestId("doc-row").filter({ hasText: uniqueTitle });

  // Ingest a fresh document (internal / all-employees defaults).
  const sourceSelect = page.getByTestId("source-select");
  await sourceSelect.selectOption({ index: 1 });
  await page.getByPlaceholder("문서 제목").fill(uniqueTitle);
  await page.getByPlaceholder(/본문/).fill("This is an e2e test document created for restore testing.");
  await expect(page.getByTestId("ingest")).toBeEnabled();
  await page.getByTestId("ingest").click();
  await expect(row()).toBeVisible({ timeout: 15_000 });

  // Archive it: disappears from the default list.
  await row().getByTestId("archive-doc").click();
  await row().getByTestId("archive-reason").fill("restore e2e setup");
  await row().getByTestId("archive-confirm").click();
  await expect(row()).toHaveCount(0);

  // Admin toggles the archived view: the doc reappears with a badge + restore
  // button (and no ACL-edit/archive buttons on an archived row).
  await page.getByTestId("show-archived-toggle").check();
  await expect(row()).toBeVisible({ timeout: 15_000 });
  await expect(row().getByTestId("archived-badge")).toBeVisible();
  await expect(row().getByTestId("restore-doc")).toBeVisible();
  await expect(row().getByTestId("acl-edit")).toHaveCount(0);
  await expect(row().getByTestId("archive-doc")).toHaveCount(0);

  // Developer role: the toggle is hidden entirely (the backend silently ignores
  // include_archived for non-admins, so exposing it would be misleading), and the
  // archived doc is not in the list.
  //
  // RoleSwitcher re-renders the OLD page with the new role before
  // window.location.reload() lands, so mark the old document and wait for the
  // real reload instead of asserting against the dying page.
  await page.evaluate(() => { (window as { __afPreReload?: boolean }).__afPreReload = true; });
  await page.getByTestId("demo-role-switcher").selectOption("developer");
  await page.waitForFunction(() => !(window as { __afPreReload?: boolean }).__afPreReload);
  await expect(page.getByRole("heading", { name: "Knowledge" })).toBeVisible();
  await expect(page.getByTestId("role-restricted-note")).toBeVisible();
  await expect(page.getByTestId("show-archived-toggle")).toHaveCount(0);
  await expect(row()).toHaveCount(0);

  // Back to admin (page reload resets the toggle; re-enable it).
  await page.evaluate(() => { (window as { __afPreReload?: boolean }).__afPreReload = true; });
  await page.getByTestId("demo-role-switcher").selectOption("admin");
  await page.waitForFunction(() => !(window as { __afPreReload?: boolean }).__afPreReload);
  await expect(page.getByRole("heading", { name: "Knowledge" })).toBeVisible();
  // Retry the toggle click: a click that lands before React hydration is wiped
  // when the controlled checkbox re-renders, so re-check until the row shows up.
  await expect(async () => {
    const toggle = page.getByTestId("show-archived-toggle");
    if (!(await toggle.isChecked())) await toggle.check();
    await expect(row()).toBeVisible({ timeout: 3_000 });
  }).toPass({ timeout: 30_000 });

  // Restore: reason prompt mirrors the archive flow, and the form carries the
  // "vectors are not resurrected, re-index needed" note.
  await row().getByTestId("restore-doc").click();
  await expect(row().getByTestId("restore-form")).toBeVisible();
  await expect(row().getByTestId("restore-note")).toBeVisible();
  await row().getByTestId("restore-reason").fill("restore e2e test");
  await row().getByTestId("restore-confirm").click();
  await expect(row().getByTestId("archived-badge")).toHaveCount(0, { timeout: 15_000 });
  await expect(row().getByTestId("restore-doc")).toHaveCount(0);

  // The restored doc is back in the NORMAL (non-archived) list.
  await page.getByTestId("show-archived-toggle").uncheck();
  await expect(row()).toBeVisible({ timeout: 15_000 });
  await expect(row().getByTestId("archive-doc")).toBeVisible();

  // Cleanup: archive it again so repeated runs don't pile up rows.
  await row().getByTestId("archive-doc").click();
  await row().getByTestId("archive-reason").fill("restore e2e cleanup");
  await row().getByTestId("archive-confirm").click();
  await expect(row()).toHaveCount(0);
});
