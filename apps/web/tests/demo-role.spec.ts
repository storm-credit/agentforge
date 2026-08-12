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
  await expect(page.getByRole("heading", { name: "지식 문서", level: 1 })).toBeVisible();

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
  await expect(page.getByRole("heading", { name: "지식 문서", level: 1 })).toBeVisible();
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
  await expect(page.getByRole("heading", { name: "지식 문서", level: 1 })).toBeVisible();
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

// GROUP-based ACL (as opposed to clearance-rank filtering, covered above).
//
// The "hr" persona is the only demo identity in a non-default group
// ("hr-restricted"); "developer" and "hr" both clear an *internal* document on
// clearance rank (internal=1 and restricted=2 are both >= internal), so a document
// whose access_groups is exactly ["hr-restricted"] can only differ between them
// because of GROUP MEMBERSHIP. That makes this a clean group-ACL assertion, not a
// clearance one.
//
// Before the identity unification these personas only existed inside the chat/builder
// ask dropdowns, so group ACL was undemonstrable outside a single chat answer; now the
// sidebar switcher applies them app-wide and the effect is visible on the document list.
test("hr persona sees a group-restricted document that developer does not (group ACL)", async ({ page }) => {
  test.setTimeout(90_000);
  await page.goto("/knowledge");
  await expect(page.getByRole("heading", { name: "지식 문서", level: 1 })).toBeVisible();

  const hrOnlyTitle = `Group ACL HR Doc ${Date.now()}`;
  const row = () => page.getByTestId("doc-row").filter({ hasText: hrOnlyTitle });

  // The switcher now offers all four unified personas (one identity control).
  const switcher = page.getByTestId("demo-role-switcher");
  await expect(switcher).toHaveValue("admin");
  await expect(switcher.locator("option")).toHaveText(["admin", "developer", "finance", "hr"]);

  // --- Admin ingests a document restricted to the "hr-restricted" GROUP, at the
  // ordinary "internal" confidentiality level (so clearance cannot explain the
  // difference between developer and hr below).
  await page.getByTestId("source-select").selectOption({ index: 1 });
  await page.getByPlaceholder("문서 제목").fill(hrOnlyTitle);
  await page.getByPlaceholder(/본문/).fill("HR-group-only e2e document body.");
  await page.getByTestId("confidentiality-select").selectOption("internal");
  await page.getByPlaceholder("접근그룹(쉼표)").fill("hr-restricted");
  await expect(page.getByTestId("ingest")).toBeEnabled();
  await page.getByTestId("ingest").click();
  await expect(row()).toBeVisible({ timeout: 15_000 });
  await expect(row().getByTestId("doc-groups")).toHaveText("hr-restricted");
  await expect(row().getByTestId("doc-confidentiality")).toHaveText("internal");

  // RoleSwitcher re-renders the OLD page before window.location.reload() lands, so
  // mark the page and wait for the real reload (same technique as knowledge-archive).
  async function switchRole(next: string) {
    await page.evaluate(() => { (window as { __afPreReload?: boolean }).__afPreReload = true; });
    await page.getByTestId("demo-role-switcher").selectOption(next);
    await page.waitForFunction(() => !(window as { __afPreReload?: boolean }).__afPreReload);
    await expect(page.getByRole("heading", { name: "지식 문서", level: 1 })).toBeVisible();
    await expect(page.getByTestId("demo-role-switcher")).toHaveValue(next);
  }

  // --- hr: in the "hr-restricted" group -> the document is visible server-side.
  await switchRole("hr");
  await expect(page.getByTestId("role-restricted-note")).toBeVisible(); // non-privileged
  await expect(page.getByTestId("acl-edit")).toHaveCount(0);
  await expect(row()).toBeVisible({ timeout: 15_000 });

  // --- developer: same clearance rank, NOT in the group -> filtered out server-side.
  await switchRole("developer");
  await expect(row()).toHaveCount(0);

  // --- finance: also non-privileged, also outside the group -> filtered out.
  await switchRole("finance");
  await expect(page.getByTestId("role-restricted-note")).toBeVisible();
  await expect(row()).toHaveCount(0);

  // --- Cleanup as admin: archive so repeated runs don't pile up rows.
  await switchRole("admin");
  await expect(row()).toBeVisible({ timeout: 15_000 });
  await row().getByTestId("archive-doc").click();
  await row().getByTestId("archive-reason").fill("group-acl e2e cleanup");
  await row().getByTestId("archive-confirm").click();
  await expect(row()).toHaveCount(0);
});

// The audit page's GET /audit/events is admin-scoped server-side (403 for other
// roles). Verifies the frontend skips the doomed fetch for non-privileged roles
// and shows the same friendly role-restricted-note pattern used on Knowledge,
// while the admin (default) role keeps seeing real events — no regression.
test("audit page shows friendly placeholder for non-privileged role, real events for admin", async ({ page }) => {
  await page.goto("/audit");
  await expect(page.getByRole("heading", { name: "감사" })).toBeVisible();

  // --- Admin (default role): real audit list, no restriction note.
  await expect(page.getByTestId("demo-role-switcher")).toHaveValue("admin");
  await expect(page.getByTestId("role-restricted-note")).toHaveCount(0);
  await expect(page.getByTestId("audit-row").first()).toBeVisible({ timeout: 15_000 });

  // --- Switch to developer (reloads the page with the developer header bundle).
  await page.getByTestId("demo-role-switcher").selectOption("developer");
  await page.waitForLoadState("load");
  await expect(page.getByRole("heading", { name: "감사" })).toBeVisible();
  await expect(page.getByTestId("demo-role-switcher")).toHaveValue("developer");

  // Friendly placeholder shown; no attempt to render the (403'd) event list/filter.
  await expect(page.getByTestId("role-restricted-note")).toBeVisible();
  await expect(page.getByTestId("audit-filter")).toHaveCount(0);
  await expect(page.getByTestId("audit-row")).toHaveCount(0);
  await expect(page.getByTestId("audit-list")).toHaveCount(0);

  // --- Switch back to admin: full view restored.
  await page.getByTestId("demo-role-switcher").selectOption("admin");
  await page.waitForLoadState("load");
  await expect(page.getByRole("heading", { name: "감사" })).toBeVisible();
  await expect(page.getByTestId("role-restricted-note")).toHaveCount(0);
  await expect(page.getByTestId("audit-row").first()).toBeVisible({ timeout: 15_000 });
});
