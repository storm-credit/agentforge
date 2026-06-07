import { test, expect } from "@playwright/test";

test("runs page renders heading", async ({ page }) => {
  await page.goto("/runs");
  await expect(page.getByRole("heading", { name: "Runs" })).toBeVisible();
});
