import { test, expect } from "@playwright/test";

test("chat page renders controls", async ({ page }) => {
  await page.goto("/chat");
  await expect(page.getByRole("heading", { name: "Chat" })).toBeVisible();
  await expect(page.getByPlaceholder("질문을 입력하세요")).toBeVisible();
});
