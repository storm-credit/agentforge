import { test, expect } from "@playwright/test";

// Requires the API + seeded documents/audit events running behind the dev server.
test("knowledge page exposes ACL edit form for a document", async ({ page }) => {
  await page.goto("/knowledge");
  await expect(page.getByRole("heading", { name: "Knowledge" })).toBeVisible();

  const firstDoc = page.getByTestId("doc-row").first();
  await expect(firstDoc).toBeVisible();
  // each doc row shows its confidentiality + an ACL edit affordance
  await expect(firstDoc.getByTestId("doc-confidentiality")).toBeVisible();
  await firstDoc.getByTestId("acl-edit").click();
  await expect(page.getByTestId("acl-form").first()).toBeVisible();
  await expect(page.getByTestId("acl-groups").first()).toBeVisible();
  await expect(page.getByTestId("acl-reason").first()).toBeVisible();
});

test("audit viewer lists events", async ({ page }) => {
  await page.goto("/audit");
  await expect(page.getByRole("heading", { name: "Audit" })).toBeVisible();
  // seeded DB has audit events from prior activity
  await expect(page.getByTestId("audit-row").first()).toBeVisible();
});
