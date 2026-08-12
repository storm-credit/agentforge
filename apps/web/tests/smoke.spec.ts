import { expect, test } from "@playwright/test";

const routes = [
  { path: "/", heading: "사내 문서로 답하는 에이전트, 부서에서 직접 만들고 운영합니다" },
  { path: "/agents", heading: "에이전트" },
  { path: "/knowledge", heading: "지식" },
  { path: "/eval", heading: "품질 평가" },
  { path: "/audit", heading: "감사" },
  { path: "/admin/settings", heading: "설정" },
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

    const primaryNav = page.getByLabel("주 메뉴");

    await primaryNav.getByRole("link", { name: "에이전트", exact: true }).click();
    await expect(page.getByRole("heading", { name: "에이전트", exact: true })).toBeVisible();

    await primaryNav.getByRole("link", { name: "지식", exact: true }).click();
    await expect(page.getByRole("heading", { name: "지식", exact: true })).toBeVisible();

    await primaryNav.getByRole("link", { name: "감사", exact: true }).click();
    await expect(page.getByRole("heading", { name: "감사", exact: true })).toBeVisible();
  });
});
