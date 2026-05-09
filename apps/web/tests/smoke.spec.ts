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
});
