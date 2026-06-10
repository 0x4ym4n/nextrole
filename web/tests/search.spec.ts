import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
test("real API search, details, save and reload", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Role or skills").fill("Engineer");
  await page.getByRole("button", { name: "Find my next role" }).click();
  await expect(page.locator(".job").first()).toBeVisible();
  await page.locator(".explain").first().click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByText("Why this role appeared")).toBeVisible();
  await page.getByLabel("Close details").click();
  await page.locator(".save").first().click();
  await page.getByRole("button", { name: /^Saved/ }).click();
  await expect(page.locator(".job")).toHaveCount(1);
  await page.reload();
  await page.getByRole("button", { name: /^Saved/ }).click();
  await expect(page.locator(".job")).toHaveCount(1);
});
test("empty results, unknown attributes and errors", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Role or skills").fill("zzqq_nonexistent_occupation");
  await page.getByText("Recommendation settings").click();
  await page.getByLabel("Ranking strategy").selectOption("exact");
  await page.getByRole("button", { name: "Find my next role" }).click();
  await expect(
    page.getByText("No matches for these preferences."),
  ).toBeVisible();
  await page.route("**/api/v1/search", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: '{"error":"Model temporarily unavailable"}',
    }),
  );
  await page.getByLabel("Role or skills").fill("Developer");
  await page.getByRole("button", { name: "Find my next role" }).click();
  await expect(page.locator('.error[role="alert"]')).toContainText(
    "Model temporarily unavailable",
  );
});
test("pagination preserves submitted preferences", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Role or skills").fill("Engineer");
  await page.getByRole("button", { name: "Find my next role" }).click();
  await expect(page.locator(".job").first()).toBeVisible();
  if (
    await page.getByRole("button", { name: "Load more opportunities" }).count()
  ) {
    const n = await page.locator(".job").count();
    await page.getByLabel("Role or skills").fill("Nurse");
    const req = page.waitForRequest(
      (r) => r.url().endsWith("/api/v1/search") && r.method() === "POST",
    );
    await page.getByRole("button", { name: "Load more opportunities" }).click();
    expect((await req).postDataJSON().query).toBe("Engineer");
    await expect.poll(() => page.locator(".job").count()).toBeGreaterThan(n);
  } else {
    throw Error("Test corpus must return multiple pages for Engineer");
  }
});
test("desktop accessibility and real screenshot", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1100 });
  await page.goto("/");
  await page.getByLabel("Role or skills").fill("Engineer");
  await page.getByRole("button", { name: "Find my next role" }).click();
  await expect(page.locator(".job").first()).toBeVisible();
  const audit = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(audit.violations).toEqual([]);
  await page.screenshot({
    path: "../evidence/web-desktop.png",
    fullPage: true,
  });
});
test("390px Arabic layout and keyboard dialog", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.getByRole("button", { name: "العربية", exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await page.locator("#role").fill("مهندس");
  await page.locator("button[type=submit]").click();
  await expect(page.locator(".status")).not.toHaveText("جار البحث…");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: "../evidence/web-mobile-arabic.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "English", exact: true }).click();
  await page.locator("#role").fill("Engineer");
  await page.locator("button[type=submit]").click();
  await expect(page.locator(".job").first()).toBeVisible();
  await page.locator(".explain").first().click();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).not.toBeVisible();
});
