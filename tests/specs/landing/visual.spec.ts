import { test, expect } from "@playwright/test";

test.describe("Landing page — visual regression (redesigned sections)", () => {
  // ── Reveal section ────────────────────────────────────────────────────────

  test("Reveal section — desktop", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/");
    const reveal = page.locator("#reveal");
    await reveal.scrollIntoViewIfNeeded();
    await expect(reveal).toHaveScreenshot("reveal-desktop.png", {
      maxDiffPixels: 100,
    });
  });

  test("Reveal section — mobile", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/");
    const reveal = page.locator("#reveal");
    await reveal.scrollIntoViewIfNeeded();
    await expect(reveal).toHaveScreenshot("reveal-mobile.png", {
      maxDiffPixels: 100,
    });
  });

  // ── How It Helps section ──────────────────────────────────────────────────

  test("How It Helps — desktop", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/");
    const how = page.locator("#how");
    await how.scrollIntoViewIfNeeded();
    await expect(how).toHaveScreenshot("how-desktop.png", {
      maxDiffPixels: 100,
    });
  });

  test("How It Helps — mobile", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/");
    const how = page.locator("#how");
    await how.scrollIntoViewIfNeeded();
    await expect(how).toHaveScreenshot("how-mobile.png", {
      maxDiffPixels: 100,
    });
  });

  test("How It Helps — reduced motion (all steps visible)", async ({
    page,
  }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/");
    const how = page.locator("#how");
    await how.scrollIntoViewIfNeeded();
    // Verify section is visible and fully rendered with reduced motion
    await expect(how).toBeVisible();
    // Check pipeline steps if they carry data-testid; gracefully skip if absent
    const steps = how.locator("[data-testid='pipeline-step']");
    const stepCount = await steps.count();
    if (stepCount > 0) {
      // All steps must be visible — none stuck in a hidden/pending state
      for (let i = 0; i < stepCount; i++) {
        await expect(steps.nth(i)).toBeVisible();
      }
    }
    await expect(how).toHaveScreenshot("how-reduced-motion.png", {
      maxDiffPixels: 100,
    });
  });

  // ── Why BioShield section ─────────────────────────────────────────────────

  test("Why BioShield — desktop", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/");
    const why = page.locator("#why");
    await why.scrollIntoViewIfNeeded();
    await expect(why).toHaveScreenshot("why-desktop.png", {
      maxDiffPixels: 100,
    });
  });

  test("Why BioShield — mobile", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/");
    const why = page.locator("#why");
    await why.scrollIntoViewIfNeeded();
    await expect(why).toHaveScreenshot("why-mobile.png", {
      maxDiffPixels: 100,
    });
  });
});
