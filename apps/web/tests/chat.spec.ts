import { test, expect } from "@playwright/test";

test("chat page renders controls", async ({ page }) => {
  await page.goto("/chat");
  await expect(page.getByRole("heading", { name: "Chat" })).toBeVisible();
  await expect(page.getByPlaceholder("질문을 입력하세요")).toBeVisible();
});

test("failed ask shows a distinct error, not a fake answer", async ({ page }) => {
  // Mock /agents so the page gets an agentId (and the ask button becomes enabled)
  // without depending on a live backend, and force the ask POST to /runs to fail,
  // simulating a network/API failure.
  await page.route("**/api/v1/agents", (route) => {
    if (route.request().method() === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([{ id: "mock-agent-1", name: "Mock", purpose: "", owner_department: "Ops", status: "published" }]),
      });
    }
    return route.continue();
  });
  await page.route("**/api/v1/runs", (route) => {
    if (route.request().method() === "POST") {
      return route.fulfill({ status: 500, body: "internal error" });
    }
    return route.continue();
  });

  await page.goto("/chat");
  await page.getByPlaceholder("질문을 입력하세요").fill("연차 며칠 남았어?");
  await page.getByRole("button", { name: "질문" }).click();

  await expect(page.getByTestId("ask-error")).toBeVisible();
  await expect(page.getByTestId("answer")).toHaveCount(0);
});
