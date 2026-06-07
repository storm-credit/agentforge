import { test, expect } from "@playwright/test";

test("knowledge page shows add-document form and disables submit until valid", async ({ page }) => {
  await page.goto("/knowledge");
  await expect(page.getByRole("heading", { name: "Knowledge" })).toBeVisible();
  await expect(page.getByPlaceholder("문서 제목")).toBeVisible();
  await expect(page.getByTestId("ingest")).toBeDisabled();
});
