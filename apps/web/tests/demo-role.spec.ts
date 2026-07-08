import { test, expect } from "@playwright/test";

// Requires the API + Postgres + Qdrant running behind the dev server.
//
// Verifies the demo-role switcher end to end:
//  1. admin (default) sees privileged controls (ACL edit / archive) on the knowledge page;
//  2. switching to "developer" (a) hides those controls (UX gating) and (b) genuinely
//     filters the document list SERVER-SIDE: developer's clearance is "internal" (rank 1),
//     so a "restricted" document (rank 2, clearance too low) disappears from the list while
//     a "public" document (rank 0, clearance more than sufficient) stays visible.
//  3. switching back to "admin" restores the full view.
//
// Creates its own documents (unique titles) so it does not disturb other specs.
test("demo role switcher changes privileged controls and server-scoped lists", async ({ page }) => {
  test.setTimeout(90_000);
  await page.goto("/knowledge");
  await expect(page.getByRole("heading", { name: "Knowledge" })).toBeVisible();

  const stamp = Date.now();
  const publicTitle = `Demo Role Public Doc ${stamp}`;
  const restrictedTitle = `Demo Role Restricted Doc ${stamp}`;

  // Pick the first existing knowledge source (default "기존 선택" mode).
  const sourceSelect = page.getByTestId("source-select");
  await sourceSelect.selectOption({ index: 1 });

  // --- Ingest a PUBLIC document (visible to the internal-clearance developer role).
  await page.getByPlaceholder("문서 제목").fill(publicTitle);
  await page.getByPlaceholder(/본문/).fill("Public demo-role e2e document body.");
  await page.getByTestId("confidentiality-select").selectOption("public");
  await expect(page.getByTestId("ingest")).toBeEnabled();
  await page.getByTestId("ingest").click();
  const publicRow = page.getByTestId("doc-row").filter({ hasText: publicTitle });
  await expect(publicRow).toBeVisible({ timeout: 15_000 });

  // --- Ingest a RESTRICTED document (should vanish for internal-clearance developer).
  await page.getByRole("button", { name: "다른 문서 추가" }).click();
  await page.getByPlaceholder("문서 제목").fill(restrictedTitle);
  await page.getByPlaceholder(/본문/).fill("Restricted demo-role e2e document body.");
  await page.getByTestId("confidentiality-select").selectOption("restricted");
  await expect(page.getByTestId("ingest")).toBeEnabled();
  await page.getByTestId("ingest").click();
  const restrictedRow = page.getByTestId("doc-row").filter({ hasText: restrictedTitle });
  await expect(restrictedRow).toBeVisible({ timeout: 15_000 });

  // --- Admin (default role): privileged controls visible on both rows.
  await expect(page.getByTestId("demo-role-switcher")).toHaveValue("admin");
  await expect(publicRow.getByTestId("acl-edit")).toBeVisible();
  await expect(publicRow.getByTestId("archive-doc")).toBeVisible();
  await expect(page.getByTestId("role-restricted-note")).toHaveCount(0);

  // --- Switch to developer (reloads the page with the developer header bundle).
  await page.getByTestId("demo-role-switcher").selectOption("developer");
  await page.waitForLoadState("load");
  await expect(page.getByRole("heading", { name: "Knowledge" })).toBeVisible();
  await expect(page.getByTestId("demo-role-switcher")).toHaveValue("developer");

  // Server-side ACL scoping: the restricted doc is gone, the public doc remains.
  await expect(page.getByTestId("doc-row").filter({ hasText: publicTitle }))
    .toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("doc-row").filter({ hasText: restrictedTitle })).toHaveCount(0);

  // UX gating: privileged controls hidden; restricted-view note shown.
  await expect(page.getByTestId("acl-edit")).toHaveCount(0);
  await expect(page.getByTestId("archive-doc")).toHaveCount(0);
  await expect(page.getByTestId("role-restricted-note")).toBeVisible();

  // --- Switch back to admin: full view restored.
  await page.getByTestId("demo-role-switcher").selectOption("admin");
  await page.waitForLoadState("load");
  await expect(page.getByRole("heading", { name: "Knowledge" })).toBeVisible();
  await expect(page.getByTestId("demo-role-switcher")).toHaveValue("admin");

  const restoredRestrictedRow = page.getByTestId("doc-row").filter({ hasText: restrictedTitle });
  await expect(restoredRestrictedRow).toBeVisible({ timeout: 15_000 });
  await expect(restoredRestrictedRow.getByTestId("acl-edit")).toBeVisible();
  await expect(restoredRestrictedRow.getByTestId("archive-doc")).toBeVisible();

  // Cleanup: archive both e2e documents so repeated runs don't pile up rows.
  for (const title of [restrictedTitle, publicTitle]) {
    const row = page.getByTestId("doc-row").filter({ hasText: title });
    await row.getByTestId("archive-doc").click();
    await row.getByTestId("archive-reason").fill("demo-role e2e cleanup");
    await row.getByTestId("archive-confirm").click();
    await expect(page.getByTestId("doc-row").filter({ hasText: title })).toHaveCount(0);
  }
});
