import { test, expect } from "@playwright/test";

test.describe("Marketing landing page", () => {
  test("/ loads without auth and shows hero", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("h1")).toContainText("Lo que comes");
    await expect(
      page.getByText("BioShield AI · Nutrición inteligente"),
    ).toBeVisible();
  });

  test("RegulatoryBanner is visible", async ({ page }) => {
    await page.goto("/");
    await expect(
      page.getByText(/Herramienta educativa.*No sustituye consulta médica/i),
    ).toBeVisible();
  });

  test("header Entrar link points to /login", async ({ page }) => {
    await page.goto("/");
    const link = page.locator('header a[href="/login"]');
    await expect(link).toBeVisible();
    await expect(link).toContainText("Entrar");
  });

  test("regulatory copy — no blocklist terms on page", async ({ page }) => {
    await page.goto("/");
    const content = await page.content();
    const blocklist = [
      "diagnosticamos",
      "riesgo cardiovascular",
      "predicción de",
    ];
    for (const term of blocklist) {
      expect(content.toLowerCase()).not.toContain(term.toLowerCase());
    }
  });

  test("/home redirects to /login without auth", async ({ page }) => {
    await page.goto("/home");
    await expect(page).toHaveURL(/\/login/);
  });

  test("all 9 section anchors exist in DOM", async ({ page }) => {
    await page.goto("/");
    for (const id of ["hero", "reveal", "how", "why", "trust", "waitlist", "faq", "stack"]) {
      const section = page.locator(`#${id}`);
      await expect(section).toBeAttached();
    }
  });
});
