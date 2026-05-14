import { expect, test } from "@playwright/test";

const routes = [
  { path: "/", heading: "Agent readiness control" },
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
    await expect(primaryNav.getByRole("link", { name: "Agents", exact: true })).toHaveAttribute(
      "aria-current",
      "page",
    );

    await primaryNav.getByRole("link", { name: "Knowledge", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Knowledge", exact: true })).toBeVisible();

    await primaryNav.getByRole("link", { name: "Audit", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Audit", exact: true })).toBeVisible();
  });

  test("knowledge flow supports local upload, index queue, and retrieval preview", async ({ page }) => {
    await page.route("**/api/**", async (route) => {
      await route.fulfill({ status: 404, body: "Not found" });
    });

    await page.goto("/knowledge");

    await expect(page.getByRole("heading", { name: "Knowledge", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: /Policy library/ })).toBeVisible();

    await page.getByLabel("Document title").fill("Q2 support policy addendum");
    await page.getByLabel("Checksum").fill("sha256:test-addendum");
    await page.getByRole("button", { name: "Upload document" }).click();

    await expect(page.getByText("Q2 support policy addendum", { exact: true })).toBeVisible();
    await expect(page.getByText(/Registered Q2 support policy addendum locally/)).toBeVisible();

    await page.getByRole("button", { name: "Queue index" }).click();
    await expect(page.getByText(/Queued .* document\(s\) locally/)).toBeVisible();

    await page.getByLabel("Question").fill("How should refund exceptions be answered?");
    await page.getByRole("button", { name: "Preview retrieval" }).click();

    await expect(page.getByText(/Retrieval preview is using local ranking/)).toBeVisible();
    await expect(
      page.locator(".retrievalResults").getByText("Refund exception policy", { exact: true }).first(),
    ).toBeVisible();
  });

  test("eval workflow supports suite filtering and trace citation review", async ({ page }) => {
    await page.route("**/api/**", async (route) => {
      await route.fulfill({ status: 404, body: "Not found" });
    });

    await page.goto("/eval");

    await expect(page.getByRole("heading", { name: "Evaluation", exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Synthetic corpus suites" })).toBeVisible();
    await expect(page.getByText(/Eval reports are persisted through \/api\/v1\/eval/)).toBeVisible();

    await page.getByRole("button", { name: "Sync API" }).click();
    await expect(page.getByText(/Persisted eval report unavailable/)).toBeVisible();

    await page.getByRole("button", { name: /Citation integrity/ }).click();
    await page.getByRole("button", { name: /cit_003/ }).click();

    await expect(page.getByRole("heading", { name: "Trace and citations" })).toBeVisible();
    await expect(page.getByText(/Matched expected answer path/)).toBeVisible();
    await expect(page.getByText("Expense Reimbursement Policy")).toBeVisible();
    await expect(page.getByText("citation_validator")).toBeVisible();
  });

  test("audit page does not imply a queryable audit API yet", async ({ page }) => {
    await page.goto("/audit");

    await expect(page.getByRole("heading", { name: "Audit", exact: true })).toBeVisible();
    await expect(page.getByText("Audit read API pending")).toBeVisible();
    await expect(page.getByText("eval_run.created")).toBeVisible();
    await expect(page.getByText("audit.search_api")).toBeVisible();
  });

  test("agent rows drive the selected governance detail panel", async ({ page }) => {
    await page.goto("/agents");

    await page.getByRole("button", { name: /Security Policy Assistant/ }).click();

    await expect(
      page.getByRole("heading", { name: "Security Policy Assistant", exact: true }),
    ).toBeVisible();
    await expect(page.getByText("Run ACL suite", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: /Security Policy Assistant/ })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  test("locked release policies expose real switch semantics", async ({ page }) => {
    await page.goto("/admin/settings");

    await expect(page.getByRole("switch", { name: "Citation required locked on" })).toBeChecked();
    await expect(page.getByRole("switch", { name: "ACL filter required locked on" })).toBeChecked();
  });

  test("mobile console layout avoids horizontal overflow", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/agents");

    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);

    expect(overflow).toBe(false);
  });
});
