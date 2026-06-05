import { test, expect } from "@playwright/test";

test("builder renders guided sections and disables publish until valid", async ({ page }) => {
  await page.goto("/agents/new");
  await expect(page.getByRole("heading", { name: "에이전트 만들기" })).toBeVisible();
  await expect(page.getByPlaceholder("이름 (예: 사내 도우미)")).toBeVisible();
  await expect(page.getByTestId("publish")).toBeDisabled();
  await expect(page.getByText("게시하면 활성화")).toBeVisible();
});
