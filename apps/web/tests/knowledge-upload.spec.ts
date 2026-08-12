import { test, expect } from "@playwright/test";

test("knowledge page shows add-document form and disables submit until valid", async ({ page }) => {
  await page.goto("/knowledge");
  await expect(page.getByRole("heading", { name: "지식 문서", level: 1 })).toBeVisible();
  await expect(page.getByPlaceholder("문서 제목")).toBeVisible();
  await expect(page.locator('input[type="file"]')).toHaveAttribute("accept", ".txt,.md,.pdf,.docx");
  await expect(page.getByTestId("ingest")).toBeDisabled();
});
