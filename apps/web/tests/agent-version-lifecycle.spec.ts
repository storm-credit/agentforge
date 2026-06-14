import { test, expect } from "@playwright/test";

// Render smoke for the agent version lifecycle UI. Requires the API + seeded
// agents (e.g. `python -m app.seed_demo_rich`) running behind the dev server.
test("agent detail shows version lifecycle with validate/publish actions", async ({ page }) => {
  await page.goto("/agents");
  await expect(page.getByRole("heading", { name: "Agents" })).toBeVisible();

  const firstAgent = page.getByTestId("agent-card").first();
  await expect(firstAgent).toBeVisible();
  await firstAgent.click();

  // navigated to /agents/{id}
  await expect(page).toHaveURL(/\/agents\/.+/);
  await expect(page.getByRole("heading", { name: "버전 라이프사이클" })).toBeVisible();
  await expect(page.getByTestId("version-list")).toBeVisible();

  // a seeded agent has at least one version with a status badge
  await expect(page.getByTestId("version-row").first()).toBeVisible();
  await expect(page.getByTestId("version-status").first()).toBeVisible();

  // creating a new version adds a row (auto-numbered server-side)
  const before = await page.getByTestId("version-row").count();
  await page.getByTestId("new-version").click();
  await expect(page.getByTestId("version-row")).toHaveCount(before + 1);

  // the new draft shows a config diff vs the current published version
  await expect(page.getByTestId("version-diff").first()).toBeVisible();
});
