import { expect, test } from "@playwright/test";

const routes = [
  { path: "/", heading: "Governed agent build workspace" },
  { path: "/agents", heading: "Agents" },
  { path: "/knowledge", heading: "Knowledge" },
  { path: "/eval", heading: "Evaluation" },
  { path: "/audit", heading: "Audit" },
  { path: "/admin/settings", heading: "Settings" },
];

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
});
