import { test, expect } from "@playwright/test";

test("runs page renders heading", async ({ page }) => {
  await page.goto("/runs");
  await expect(page.getByRole("heading", { name: "Runs" })).toBeVisible();
});

// Requires the API + at least one seeded run behind the dev server.
test("runs page surfaces guardrail signals as badges, not just raw JSON", async ({ page }) => {
  await page.goto("/runs");
  await expect(page.getByRole("heading", { name: "Runs" })).toBeVisible();

  // The first run auto-selects on load; guardrail badges render once steps load.
  await expect(page.getByTestId("guardrail-signals").first()).toBeVisible();
  await expect(page.getByTestId("guardrail-pii").first()).toBeVisible();
  await expect(page.getByTestId("guardrail-citation").first()).toBeVisible();
  await expect(page.getByTestId("guardrail-confidence").first()).toBeVisible();
  await expect(page.getByTestId("guardrail-grounding").first()).toBeVisible();
});
